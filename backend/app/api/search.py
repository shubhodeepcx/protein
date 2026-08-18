from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from fastapi import APIRouter, HTTPException, Query

from app.models.search import ALL_SOURCES, SearchResponse, SearchResult, SourceFilter, SourceName
from app.services.alphafold import AlphaFoldClient
from app.services.rcsb import RCSBClient
from app.services.uniprot import UniProtClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

MAX_QUERY_CHARS = 200


class SourceClient(Protocol):
    """The uniform contract every external database client satisfies."""

    async def search(self, query: str) -> list[SearchResult]: ...

    async def fetch_metadata(self, protein_id: str) -> dict: ...

    async def download_structure(self, protein_id: str) -> tuple[bytes, str]: ...


# Module-level singletons so the per-client metadata caches survive between
# requests (spec 5.4: LRU 256 / TTL 1h). They hold no per-request state.
_UNIPROT = UniProtClient()
_CLIENTS: dict[SourceName, SourceClient] = {
    "rcsb": RCSBClient(),
    "alphafold": AlphaFoldClient(uniprot=_UNIPROT),
    "uniprot": _UNIPROT,
}


def get_client(source: SourceName) -> SourceClient:
    """Look up the client for a source. Adding a source means one dict entry."""
    return _CLIENTS[source]


@router.get("", response_model=SearchResponse)
async def search_databases(
    q: str = Query(..., description="Free-text query."),
    source: SourceFilter = Query("all", description="Which database(s) to query."),
) -> SearchResponse:
    """Fan out a free-text query across the public protein databases.

    A source that raises never fails the request: its name lands in
    `failed_sources` and the other sources' hits are still returned
    (spec section 7).
    """
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query 'q' must not be empty.")
    if len(query) > MAX_QUERY_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Query 'q' is too long (max {MAX_QUERY_CHARS} characters).",
        )

    sources: tuple[SourceName, ...] = ALL_SOURCES if source == "all" else (source,)
    outcomes = await asyncio.gather(
        *(get_client(name).search(query) for name in sources),
        return_exceptions=True,
    )

    results: list[SearchResult] = []
    failed_sources: list[SourceName] = []
    seen: set[tuple[str, str]] = set()

    for name, outcome in zip(sources, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning("Search source %s failed for %r: %r", name, query, outcome)
            failed_sources.append(name)
            continue
        for result in outcome:
            key = (result.source, result.source_id.upper())
            if key in seen:
                logger.debug("Dropping duplicate search hit %s:%s", *key)
                continue
            seen.add(key)
            results.append(result)

    return SearchResponse(query=query, results=results, failed_sources=failed_sources)
