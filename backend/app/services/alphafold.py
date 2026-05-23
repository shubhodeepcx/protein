from __future__ import annotations

SearchResult = dict[str, str | int | float | bool | None]
Metadata = dict[str, object]


class AlphaFoldClient:
    """Async AlphaFold DB client stub."""

    async def search(self, query: str) -> list[SearchResult]:
        raise NotImplementedError

    async def fetch_metadata(self, protein_id: str) -> Metadata:
        raise NotImplementedError

    async def download_structure(self, protein_id: str) -> tuple[bytes, str]:
        raise NotImplementedError
