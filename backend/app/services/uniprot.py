from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.models.search import SearchResult
from app.services.cache import TTLCache
from app.services.external import (
    MAX_RESULTS_PER_SOURCE,
    Metadata,
    SourceNotFoundError,
    SourceUnavailableError,
    as_int,
    new_client,
    to_search_result,
)

logger = logging.getLogger(__name__)

SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"

# Only ask for the fields we actually render — a bare UniProtKB entry is ~100 kB.
SEARCH_FIELDS = "accession,id,protein_name,organism_name,length,xref_alphafolddb,cc_function"

# UniProt's own accession pattern (see https://www.uniprot.org/help/accession_numbers),
# optionally followed by an isoform suffix such as "-2".
_ACCESSION_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})(-[0-9]+)?$"
)

# Function comments run to several paragraphs; cards only have room for a blurb.
_DESCRIPTION_CHARS = 320


class UniProtClient:
    """Async client for the UniProtKB REST API.

    UniProt hosts no coordinates of its own, so `download_structure` follows the
    entry's AlphaFoldDB cross-reference and delegates to `AlphaFoldClient`.
    """

    source = "uniprot"

    def __init__(self, cache: TTLCache[Metadata] | None = None) -> None:
        self._cache: TTLCache[Metadata] = cache if cache is not None else TTLCache()

    # ---------------------------------------------------------------- search

    async def search(self, query: str) -> list[SearchResult]:
        entries = await self.search_entries(query)
        return [to_search_result(meta) for meta in entries]

    async def search_entries(
        self, query: str, *, alphafold_only: bool = False
    ) -> list[Metadata]:
        """Run a UniProtKB search and return normalised metadata dicts.

        `alphafold_only` adds UniProt's own `(database:alphafolddb)` filter,
        which is how `AlphaFoldClient.search` resolves a free-text query into
        accessions that actually have a predicted model.
        """
        lucene = f"({query}) AND (database:alphafolddb)" if alphafold_only else query
        params: dict[str, Any] = {
            "query": lucene,
            "format": "json",
            "size": MAX_RESULTS_PER_SOURCE,
            "fields": SEARCH_FIELDS,
        }
        async with new_client() as client:
            try:
                response = await client.get(SEARCH_URL, params=params)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"UniProt search request failed: {exc}") from exc

        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"UniProt search returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError("UniProt search returned non-JSON body") from exc

        raw_results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(raw_results, list):
            raise SourceUnavailableError("UniProt search returned an unexpected payload")

        total = as_int(response.headers.get("x-total-results"))
        if total is not None and total > len(raw_results):
            logger.info(
                "UniProt search for %r matched %d entries; kept the first %d",
                query,
                total,
                len(raw_results),
            )

        return [_normalise(entry) for entry in raw_results if isinstance(entry, dict)]

    # -------------------------------------------------------------- metadata

    async def fetch_metadata(self, protein_id: str) -> Metadata:
        accession = normalise_accession(protein_id)
        cached = self._cache.get(accession)
        if cached is not None:
            return cached

        async with new_client() as client:
            try:
                response = await client.get(ENTRY_URL.format(accession=accession))
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"UniProt entry request failed: {exc}") from exc

        if response.status_code in (400, 404):
            raise SourceNotFoundError(f"UniProt has no entry for accession {accession}")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"UniProt entry {accession} returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError("UniProt entry returned non-JSON body") from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError("UniProt entry returned an unexpected payload")

        meta = _normalise(body)
        self._cache.put(accession, meta)
        return meta

    # ------------------------------------------------------------- structure

    async def download_structure(self, protein_id: str) -> tuple[bytes, str]:
        """Follow the AlphaFoldDB cross-reference and download that model.

        UniProt itself serves no coordinates; spec 5.4 defines "download from
        UniProt" as following the AlphaFold cross-ref.
        """
        # Imported here rather than at module scope: AlphaFoldClient imports
        # UniProtClient for its search, so a top-level import would cycle.
        from app.services.alphafold import AlphaFoldClient

        accession = normalise_accession(protein_id)
        meta = await self.fetch_metadata(accession)
        af_accession = meta.get("alphafold_accession")
        if not isinstance(af_accession, str) or not af_accession:
            raise SourceNotFoundError(
                f"UniProt entry {accession} has no AlphaFold model to import"
            )
        return await AlphaFoldClient().download_structure(af_accession)


def normalise_accession(protein_id: str) -> str:
    accession = protein_id.strip().upper()
    if not _ACCESSION_RE.match(accession):
        raise SourceNotFoundError(f"{protein_id!r} is not a valid UniProt accession")
    return accession


def _normalise(entry: Metadata) -> Metadata:
    """Flatten a UniProtKB entry (search hit or full record) into our shape."""
    accession = entry.get("primaryAccession")
    organism = (entry.get("organism") or {}).get("scientificName")
    cross_refs = entry.get("uniProtKBCrossReferences") or []

    alphafold_accession: str | None = None
    pdb_ids: list[str] = []
    if isinstance(cross_refs, list):
        for ref in cross_refs:
            if not isinstance(ref, dict):
                continue
            database = ref.get("database")
            ref_id = ref.get("id")
            if not isinstance(ref_id, str):
                continue
            if database == "AlphaFoldDB" and alphafold_accession is None:
                alphafold_accession = ref_id
            elif database == "PDB":
                pdb_ids.append(ref_id)

    return {
        "source": "uniprot",
        "source_id": str(accession) if accession else "",
        "title": _protein_name(entry),
        "organism": organism if isinstance(organism, str) else None,
        "description": _function_comment(entry),
        "resolution": None,
        "method": None,
        "release_year": None,
        "sequence_length": as_int((entry.get("sequence") or {}).get("length")),
        "confidence": None,
        "uniprot_id": entry.get("uniProtkbId"),
        "alphafold_accession": alphafold_accession,
        "pdb_ids": pdb_ids,
    }


def _protein_name(entry: Metadata) -> str | None:
    description = entry.get("proteinDescription") or {}
    recommended = description.get("recommendedName") or {}
    full = (recommended.get("fullName") or {}).get("value")
    if isinstance(full, str) and full.strip():
        return full.strip()
    submitted = description.get("submissionNames") or []
    if isinstance(submitted, list) and submitted:
        value = ((submitted[0] or {}).get("fullName") or {}).get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _function_comment(entry: Metadata) -> str | None:
    comments = entry.get("comments") or []
    if not isinstance(comments, list):
        return None
    for comment in comments:
        if not isinstance(comment, dict) or comment.get("commentType") != "FUNCTION":
            continue
        for text in comment.get("texts") or []:
            value = (text or {}).get("value")
            if isinstance(value, str) and value.strip():
                trimmed = value.strip()
                if len(trimmed) > _DESCRIPTION_CHARS:
                    trimmed = trimmed[: _DESCRIPTION_CHARS - 1].rstrip() + "…"
                return trimmed
    return None
