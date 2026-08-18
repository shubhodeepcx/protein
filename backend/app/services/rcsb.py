from __future__ import annotations

import asyncio
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
    as_float,
    as_int,
    new_client,
    to_search_result,
    year_from_iso,
)

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
POLYMER_ENTITY_URL = "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"
FILE_URL = "https://files.rcsb.org/download/{pdb_id}.cif"

# PDB entry IDs are 4 alphanumerics starting with a digit (e.g. 1CRN, 4HHB).
_PDB_ID_RE = re.compile(r"^[0-9][A-Za-z0-9]{3}$")

# Concurrency bound on the per-hit metadata enrichment so one search never
# fires 50 simultaneous requests at data.rcsb.org.
_ENRICH_CONCURRENCY = 8


class RCSBClient:
    """Async client for the RCSB PDB Search + Data + File-download APIs.

    Interface mirrors `AlphaFoldClient` and `UniProtClient`: `search`,
    `fetch_metadata`, `download_structure`. Adding a fourth source means one
    new sibling module with the same three coroutines and no caller changes.
    """

    source = "rcsb"

    def __init__(self, cache: TTLCache[Metadata] | None = None) -> None:
        # Spec 5.4: metadata calls are cached (LRU 256 / TTL 1h); search and
        # structure download deliberately bypass the cache.
        self._cache: TTLCache[Metadata] = cache if cache is not None else TTLCache()

    # ---------------------------------------------------------------- search

    async def search(self, query: str) -> list[SearchResult]:
        """Full-text search the PDB, then enrich each hit with entry metadata.

        The Search API only returns `{identifier, score}` per hit, so titles,
        organisms, and resolutions come from a follow-up Data API call per hit.
        """
        payload: dict[str, Any] = {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": query},
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": MAX_RESULTS_PER_SOURCE},
                "results_content_type": ["experimental"],
                "sort": [{"sort_by": "score", "direction": "desc"}],
            },
        }

        async with new_client() as client:
            try:
                response = await client.post(SEARCH_URL, json=payload)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"RCSB search request failed: {exc}") from exc

            # RCSB answers a zero-hit query with 204 No Content.
            if response.status_code == 204:
                return []
            if response.status_code >= 400:
                raise SourceUnavailableError(
                    f"RCSB search returned HTTP {response.status_code}"
                )
            try:
                body = response.json()
            except ValueError as exc:
                raise SourceUnavailableError("RCSB search returned non-JSON body") from exc

            result_set = body.get("result_set") or []
            total = as_int(body.get("total_count")) or len(result_set)
            identifiers = [
                str(hit["identifier"])
                for hit in result_set
                if isinstance(hit, dict) and hit.get("identifier")
            ]
            if total > len(identifiers):
                logger.info(
                    "RCSB search for %r matched %d entries; kept the top %d by score",
                    query,
                    total,
                    len(identifiers),
                )

            semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)

            async def enrich(pdb_id: str) -> Metadata:
                async with semaphore:
                    return await self._metadata(client, pdb_id)

            enriched = await asyncio.gather(
                *(enrich(pdb_id) for pdb_id in identifiers), return_exceptions=True
            )

        results: list[SearchResult] = []
        for pdb_id, meta in zip(identifiers, enriched, strict=True):
            if isinstance(meta, BaseException):
                # One bad entry must not sink the whole source — keep the hit
                # with just its identifier so the user can still import it.
                logger.warning("RCSB metadata enrichment failed for %s: %r", pdb_id, meta)
                results.append(SearchResult(source="rcsb", source_id=pdb_id.upper()))
                continue
            results.append(to_search_result(meta))
        return results

    # -------------------------------------------------------------- metadata

    async def fetch_metadata(self, protein_id: str) -> Metadata:
        """Normalised metadata for one PDB entry. Cached per spec 5.4."""
        async with new_client() as client:
            return await self._metadata(client, protein_id)

    async def _metadata(self, client: httpx.AsyncClient, protein_id: str) -> Metadata:
        pdb_id = _normalise_pdb_id(protein_id)
        cached = self._cache.get(pdb_id)
        if cached is not None:
            return cached

        entry = await _get_json(client, ENTRY_URL.format(pdb_id=pdb_id), what=f"entry {pdb_id}")

        # Organism lives on the polymer entity, not the entry, so fetch the
        # first polymer entity too. A failure here degrades organism to None
        # rather than failing the whole lookup.
        entity_ids = (entry.get("rcsb_entry_container_identifiers") or {}).get(
            "polymer_entity_ids"
        ) or []
        entity: Metadata = {}
        if entity_ids:
            url = POLYMER_ENTITY_URL.format(pdb_id=pdb_id, entity_id=entity_ids[0])
            try:
                entity = await _get_json(client, url, what=f"polymer entity {pdb_id}")
            except (SourceNotFoundError, SourceUnavailableError) as exc:
                logger.warning("RCSB polymer entity lookup failed for %s: %s", pdb_id, exc)

        meta = _normalise(pdb_id, entry, entity)
        self._cache.put(pdb_id, meta)
        return meta

    # ------------------------------------------------------------- structure

    async def download_structure(self, protein_id: str) -> tuple[bytes, str]:
        """Download the mmCIF for a PDB entry. Returns (content, 'cif')."""
        pdb_id = _normalise_pdb_id(protein_id)
        url = FILE_URL.format(pdb_id=pdb_id)
        async with new_client() as client:
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"RCSB file download failed: {exc}") from exc

        if response.status_code == 404:
            raise SourceNotFoundError(f"RCSB PDB has no entry {pdb_id}")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"RCSB file download for {pdb_id} returned HTTP {response.status_code}"
            )
        content = response.content
        if not content:
            raise SourceUnavailableError(f"RCSB returned an empty file for {pdb_id}")
        return content, "cif"


def _normalise_pdb_id(protein_id: str) -> str:
    pdb_id = protein_id.strip().upper()
    if not _PDB_ID_RE.match(pdb_id):
        raise SourceNotFoundError(f"{protein_id!r} is not a valid 4-character PDB ID")
    return pdb_id


async def _get_json(client: httpx.AsyncClient, url: str, *, what: str) -> Metadata:
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise SourceUnavailableError(f"RCSB request for {what} failed: {exc}") from exc
    if response.status_code == 404:
        raise SourceNotFoundError(f"RCSB PDB has no {what}")
    if response.status_code >= 400:
        raise SourceUnavailableError(f"RCSB {what} returned HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise SourceUnavailableError(f"RCSB {what} returned non-JSON body") from exc
    if not isinstance(body, dict):
        raise SourceUnavailableError(f"RCSB {what} returned an unexpected payload")
    return body


def _normalise(pdb_id: str, entry: Metadata, entity: Metadata) -> Metadata:
    """Flatten the RCSB entry + polymer-entity payloads into our common shape."""
    struct = entry.get("struct") or {}
    entry_info = entry.get("rcsb_entry_info") or {}
    accession = entry.get("rcsb_accession_info") or {}
    exptl = entry.get("exptl") or []
    refine = entry.get("refine") or []
    keywords = entry.get("struct_keywords") or {}
    polymer = entity.get("rcsb_polymer_entity") or {}
    organisms = entity.get("rcsb_entity_source_organism") or []
    entity_poly = entity.get("entity_poly") or {}

    method = entry_info.get("experimental_method")
    if not method and isinstance(exptl, list) and exptl:
        method = (exptl[0] or {}).get("method")

    resolution: float | None = None
    resolution_list = entry_info.get("resolution_combined")
    if isinstance(resolution_list, list) and resolution_list:
        resolution = as_float(resolution_list[0])
    if resolution is None and isinstance(refine, list) and refine:
        resolution = as_float((refine[0] or {}).get("ls_d_res_high"))

    organism: str | None = None
    if isinstance(organisms, list) and organisms:
        first = organisms[0] or {}
        raw = first.get("scientific_name") or first.get("ncbi_scientific_name")
        if isinstance(raw, str) and raw.strip():
            organism = raw.strip()

    title = struct.get("title") or polymer.get("pdbx_description")
    description = polymer.get("pdbx_description") or keywords.get("pdbx_keywords")
    if isinstance(description, str) and isinstance(title, str) and description == title:
        description = keywords.get("pdbx_keywords")

    length = as_int(entity_poly.get("rcsb_sample_sequence_length"))
    if length is None:
        length = as_int(entry_info.get("deposited_polymer_monomer_count"))

    return {
        "source": "rcsb",
        "source_id": pdb_id,
        "title": _clean(title),
        "organism": organism,
        "description": _clean(description),
        "resolution": resolution,
        "method": _clean(method),
        "release_year": year_from_iso(accession.get("initial_release_date")),
        "sequence_length": length,
        "confidence": None,
        "file_url": FILE_URL.format(pdb_id=pdb_id),
    }


def _clean(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
