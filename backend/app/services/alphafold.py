from __future__ import annotations

import logging

import httpx

from app.models.search import SearchResult
from app.services.cache import TTLCache
from app.services.external import (
    Metadata,
    SourceNotFoundError,
    SourceUnavailableError,
    as_float,
    as_int,
    new_client,
    to_search_result,
    year_from_iso,
)
from app.services.uniprot import UniProtClient, normalise_accession

logger = logging.getLogger(__name__)

PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/{accession}"
# Documented fallback (spec 5.4) for the rare entry whose prediction payload
# omits `pdbUrl`. The version segment is derived from the payload's own
# `latestVersion` field (see `_fallback_pdb_url`) so the guess tracks
# AlphaFold DB's model versioning instead of going stale behind a constant.
FALLBACK_PDB_URL_TEMPLATE = "https://alphafold.ebi.ac.uk/files/AF-{accession}-F1-model_v{version}.pdb"
# Used only when the prediction payload omits `latestVersion` entirely.
DEFAULT_FALLBACK_VERSION = 4


class AlphaFoldClient:
    """Async client for the AlphaFold DB prediction API.

    AlphaFold DB exposes **no free-text search endpoint** — its API is keyed by
    UniProt accession. Per spec 5.4 ("search via UniProt cross-ref"), `search`
    resolves the query through UniProtKB restricted to entries that carry an
    `AlphaFoldDB` cross-reference, and returns those accessions as AlphaFold
    hits. That keeps the search to a single upstream request instead of one
    prediction call per candidate accession.
    """

    source = "alphafold"

    def __init__(
        self,
        cache: TTLCache[Metadata] | None = None,
        uniprot: UniProtClient | None = None,
    ) -> None:
        self._cache: TTLCache[Metadata] = cache if cache is not None else TTLCache()
        self._uniprot = uniprot if uniprot is not None else UniProtClient()

    # ---------------------------------------------------------------- search

    async def search(self, query: str) -> list[SearchResult]:
        entries = await self._uniprot.search_entries(query, alphafold_only=True)
        results: list[SearchResult] = []
        for entry in entries:
            accession = entry.get("alphafold_accession") or entry.get("source_id")
            if not isinstance(accession, str) or not accession:
                continue
            results.append(
                to_search_result(
                    {
                        **entry,
                        "source": "alphafold",
                        "source_id": accession,
                        "method": "AlphaFold prediction",
                    }
                )
            )
        return results

    # -------------------------------------------------------------- metadata

    async def fetch_metadata(self, protein_id: str) -> Metadata:
        """Normalised prediction metadata for one accession. Cached per spec 5.4."""
        return await self._prediction(protein_id, use_cache=True)

    async def _prediction(self, protein_id: str, *, use_cache: bool) -> Metadata:
        """Fetch + normalise the prediction payload.

        `use_cache=False` skips the *read* only — the fresh payload still
        refreshes the entry, since newer data can never be worse than what is
        already stored. `download_structure` is the caller that needs this:
        a cached payload can carry a stale `pdbUrl`.
        """
        accession = normalise_accession(protein_id)
        if use_cache:
            cached = self._cache.get(accession)
            if cached is not None:
                return cached

        async with new_client() as client:
            try:
                response = await client.get(PREDICTION_URL.format(accession=accession))
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"AlphaFold prediction request failed: {exc}"
                ) from exc

        # 404 = no model for this accession; 400 = AlphaFold rejected the
        # identifier. Both mean "nothing to import here", not "we are broken".
        if response.status_code in (400, 404):
            raise SourceNotFoundError(f"AlphaFold DB has no model for accession {accession}")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"AlphaFold prediction for {accession} returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError("AlphaFold returned non-JSON body") from exc

        # The prediction endpoint answers with a list of model entries.
        if isinstance(body, dict):
            body = [body]
        if not isinstance(body, list) or not body or not isinstance(body[0], dict):
            raise SourceNotFoundError(f"AlphaFold DB has no model for accession {accession}")

        meta = _normalise(accession, body[0])
        self._cache.put(accession, meta)
        return meta

    # ------------------------------------------------------------- structure

    async def download_structure(self, protein_id: str) -> tuple[bytes, str]:
        """Download the predicted PDB model. Returns (content, 'pdb')."""
        accession = normalise_accession(protein_id)
        # Spec 5.4: structure download bypasses the metadata cache. This is the
        # path where a stale entry has teeth — a cached payload can hand us a
        # `pdbUrl` that has since moved, so we always re-read it here.
        meta = await self._prediction(accession, use_cache=False)

        pdb_url = meta.get("pdb_url")
        # Only the URL AlphaFold itself published is authoritative. The
        # version-derived guess below is for payloads that omit `pdbUrl`, so
        # it is genuinely a fallback and its status says nothing about
        # whether a model exists.
        authoritative = pdb_url if isinstance(pdb_url, str) and pdb_url else None
        fallback = _fallback_pdb_url(accession, meta)
        urls = [authoritative] if authoritative else []
        if fallback not in urls:
            urls.append(fallback)

        # (url, status) per attempt; status is None when the request never
        # completed at all (DNS, TLS, connect timeout, …).
        attempts: list[tuple[str, int | None]] = []
        transport_errors: list[str] = []
        async with new_client() as client:
            for url in urls:
                try:
                    response = await client.get(url)
                except httpx.HTTPError as exc:
                    # A transport error on one leg must not abort the chain: a
                    # flaky connection to the published URL should fall through
                    # to the fallback exactly as a bad status does. We only give
                    # up once every candidate is exhausted.
                    attempts.append((url, None))
                    transport_errors.append(f"{url}: {exc}")
                    logger.warning(
                        "AlphaFold file %s could not be reached for %s (%s); "
                        "trying next candidate",
                        url,
                        accession,
                        exc,
                    )
                    continue
                if response.status_code == 200 and response.content:
                    return response.content, "pdb"
                attempts.append((url, response.status_code))
                logger.warning(
                    "AlphaFold file %s returned HTTP %s for %s; trying next candidate",
                    url,
                    response.status_code,
                    accession,
                )

        statuses = [status for _, status in attempts if status is not None]

        # Classify on the whole chain, not just the last attempt. A 5xx
        # anywhere is an upstream outage; reporting it as "no model" would tell
        # the user to give up on a structure that exists.
        if any(status >= 500 for status in statuses):
            raise SourceUnavailableError(
                f"AlphaFold file download for {accession} failed upstream "
                f"(HTTP {', '.join(str(s) for s in statuses)})"
            )
        # A leg that never completed is an outage too — we learned nothing
        # about whether the model exists.
        if transport_errors:
            raise SourceUnavailableError(
                f"AlphaFold file download for {accession} could not be reached: "
                + "; ".join(transport_errors)
            )
        # Only a 404 on the URL AlphaFold published is a genuine "no model
        # file". If we never had that URL, the prediction lookup above already
        # confirmed a model record exists, so a 404 on the obsolete fallback is
        # our problem, not the user's.
        if authoritative is not None and attempts and attempts[0][1] == 404:
            raise SourceNotFoundError(f"AlphaFold DB has no model file for {accession}")
        raise SourceUnavailableError(
            f"AlphaFold file download for {accession} returned HTTP "
            f"{', '.join(str(s) for s in statuses) or 'no response'}"
        )


def _normalise(accession: str, prediction: Metadata) -> Metadata:
    """Flatten one AlphaFold prediction entry into our common shape."""
    sequence = prediction.get("sequence")
    length = len(sequence) if isinstance(sequence, str) else as_int(prediction.get("uniprotEnd"))

    gene = prediction.get("gene")
    tool = prediction.get("toolUsed")
    entry_id = prediction.get("entryId") or f"AF-{accession}-F1"
    bits = [f"AlphaFold DB model {entry_id}"]
    if isinstance(gene, str) and gene.strip():
        bits.append(f"gene {gene.strip()}")
    if isinstance(tool, str) and tool.strip():
        bits.append(tool.strip())

    organism = prediction.get("organismScientificName")
    title = prediction.get("uniprotDescription") or prediction.get("uniprotId")

    return {
        "source": "alphafold",
        "source_id": str(prediction.get("uniprotAccession") or accession),
        "title": title if isinstance(title, str) else None,
        "organism": organism if isinstance(organism, str) else None,
        "description": " · ".join(bits),
        "resolution": None,
        "method": tool if isinstance(tool, str) else "AlphaFold prediction",
        "release_year": year_from_iso(prediction.get("modelCreatedDate")),
        "sequence_length": length,
        "confidence": as_float(prediction.get("globalMetricValue")),
        "pdb_url": prediction.get("pdbUrl"),
        "cif_url": prediction.get("cifUrl"),
        "entry_id": entry_id,
        "latest_version": as_int(prediction.get("latestVersion")),
    }


def _fallback_pdb_url(accession: str, meta: Metadata) -> str:
    """Guess the file URL from the payload's own `latestVersion`.

    Falls back to `DEFAULT_FALLBACK_VERSION` only when the payload omits
    `latestVersion` entirely, so the guess tracks AlphaFold DB's model
    versioning instead of a constant that goes stale as versions roll.
    """
    version = meta.get("latest_version")
    if not isinstance(version, int) or version <= 0:
        version = DEFAULT_FALLBACK_VERSION
    return FALLBACK_PDB_URL_TEMPLATE.format(accession=accession, version=version)
