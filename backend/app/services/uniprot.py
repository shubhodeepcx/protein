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

# P6: the annotation panel's field set. UniProtKB exposes ~370 return fields;
# these are the ones the client's list maps onto (slice design section 2).
#
# Every name here was checked against UniProt's own result-fields column enum
# (ebi-uniprot/uniprot-website `src/uniprotkb/types/columnTypes.ts`, which
# documents itself as mirroring `/api/configure/uniprotkb/result-fields`).
# Two corrections came out of that check, both recorded in the decisions log:
#   * `xref_uniref` does NOT exist — UniRef is a separate dataset with its own
#     endpoint, not a UniProtKB cross-reference field. Asking for it makes the
#     whole request a 400, so "similar proteins" waits for P8.
#   * `xref_ndex` DOES exist, though the slice design filed NDEx under
#     "needs another source". It is included: it costs nothing here.
ANNOTATION_FIELD_NAMES: tuple[str, ...] = (
    # names, gene, origin
    "accession",
    "id",
    "protein_name",
    "gene_names",
    "organism_name",
    "organism_id",
    "lineage",
    "length",
    # function + catalysis
    "cc_function",
    "cc_catalytic_activity",
    # gene ontology, one field per aspect
    "go_p",
    "go_c",
    "go_f",
    "keyword",
    # localisation + membrane topology
    "cc_subcellular_location",
    "ft_transmem",
    "ft_topo_dom",
    # disease + PTM/processing
    "cc_disease",
    "cc_ptm",
    "ft_mod_res",
    "ft_signal",
    "ft_chain",
    "ft_disulfid",
    # pathway / network / proteome cross-references
    "xref_proteomes",
    "xref_reactome",
    "xref_biocyc",
    "xref_signor",
    "xref_ndex",
)

ANNOTATION_FIELDS = ",".join(ANNOTATION_FIELD_NAMES)

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

    def __init__(
        self,
        cache: TTLCache[Metadata] | None = None,
        annotation_cache: TTLCache[Metadata] | None = None,
    ) -> None:
        self._cache: TTLCache[Metadata] = cache if cache is not None else TTLCache()
        # Annotations get their own cache: the payloads have a different shape
        # (a whole UniProtKB entry, not our normalised metadata dict) and are
        # an order of magnitude larger, so sharing one LRU would let one
        # annotation lookup evict several search enrichments.
        self._annotation_cache: TTLCache[Metadata] = (
            annotation_cache if annotation_cache is not None else TTLCache()
        )

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
        """Normalised entry metadata for one accession. Cached per spec 5.4."""
        return await self._entry(protein_id, use_cache=True)

    async def _entry(self, protein_id: str, *, use_cache: bool) -> Metadata:
        """Fetch + normalise a UniProtKB entry.

        `use_cache=False` skips the *read* only; the fresh payload still
        refreshes the entry. `download_structure` needs it so a stale
        AlphaFoldDB cross-reference can never send us to the wrong model.
        """
        accession = normalise_accession(protein_id)
        if use_cache:
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

    # ----------------------------------------------------------- annotations

    async def fetch_annotations(self, protein_id: str) -> Metadata:
        """The raw UniProtKB entry, restricted to `ANNOTATION_FIELDS`.

        Returned unflattened on purpose: `services/annotations.py` owns the
        projection onto `ProteinAnnotations`, and keeping the transport here
        means that projection is a pure function over recorded JSON.

        Cached (LRU 256 / TTL 1h) — annotations change on UniProt's release
        cadence, not per request, and the panel refetches on every tab open.
        """
        accession = normalise_accession(protein_id)
        cached = self._annotation_cache.get(accession)
        if cached is not None:
            return cached

        params = {"fields": ANNOTATION_FIELDS}
        async with new_client() as client:
            try:
                response = await client.get(
                    ENTRY_URL.format(accession=accession), params=params
                )
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"UniProt annotation request failed: {exc}"
                ) from exc

        if response.status_code in (400, 404):
            # A 400 here is also how UniProt answers an unknown field name, so
            # log the distinction rather than silently reading it as "no entry".
            logger.info(
                "UniProt annotations for %s returned HTTP %d",
                accession,
                response.status_code,
            )
            raise SourceNotFoundError(f"UniProt has no entry for accession {accession}")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"UniProt annotations for {accession} returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError(
                "UniProt annotations returned non-JSON body"
            ) from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                "UniProt annotations returned an unexpected payload"
            )

        self._annotation_cache.put(accession, body)
        return body

    async def find_accession_for_pdb(self, pdb_id: str) -> str | None:
        """Resolve a PDB entry ID to a UniProt accession via UniProt's own index.

        The fallback for RCSB imports whose polymer-entity metadata carries no
        UniProt cross-reference. Returns None rather than raising when the
        search finds nothing — a structure with no UniProt counterpart is a
        normal outcome, not an error.
        """
        params: dict[str, Any] = {
            "query": f"(xref:pdb-{pdb_id})",
            "format": "json",
            "size": 1,
            "fields": "accession",
        }
        async with new_client() as client:
            try:
                response = await client.get(SEARCH_URL, params=params)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"UniProt PDB cross-reference search failed: {exc}"
                ) from exc

        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"UniProt PDB cross-reference search returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError(
                "UniProt PDB cross-reference search returned non-JSON body"
            ) from exc

        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        accession = first.get("primaryAccession") if isinstance(first, dict) else None
        return accession if isinstance(accession, str) and accession else None

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
        # Spec 5.4: structure download bypasses the metadata cache — a stale
        # cross-reference would point the download at the wrong model.
        meta = await self._entry(accession, use_cache=False)
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
        "title": recommended_protein_name(entry),
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


def recommended_protein_name(entry: Metadata) -> str | None:
    """The entry's recommended name, falling back to its first submitted name.

    Public because `services/annotations.py` needs exactly this rule — the
    annotation panel and a search card must not disagree about a protein's name.
    """
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
