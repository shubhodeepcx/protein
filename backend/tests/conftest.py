from __future__ import annotations

import pytest

from app.services import registry
from app.storage import local as storage

# Offline guarantee: every test that can reach the network is wrapped in
# `@respx.mock`, whose default `assert_all_mocked=True` turns any unmocked
# outbound request into a test failure. The handful of client tests that are
# *not* decorated assert the client rejects a malformed identifier before it
# ever builds a request.


@pytest.fixture(autouse=True)
def isolate_storage_and_cache(tmp_path, monkeypatch):
    """Per-test: redirect storage to tmp_path; clear summary cache."""
    test_root = tmp_path / "proteins"
    test_root.mkdir()
    monkeypatch.setattr(storage, "STORAGE_ROOT", test_root)
    registry.clear()
    yield
    registry.clear()


@pytest.fixture(autouse=True)
def no_retry_backoff_delay(monkeypatch):
    """Retry backoff sleeps for real in production; tests shouldn't wait for it.

    Patches the indirection in `services/resilience.py`, not `asyncio.sleep`
    itself, so this can't also stall pytest-asyncio's own scheduling.
    """

    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.resilience._sleep", instant)


@pytest.fixture(autouse=True)
def fresh_search_clients(monkeypatch):
    """Per-test: swap in fresh external clients so metadata caches never leak.

    `app.api.search` keeps module-level singletons on purpose (their TTL caches
    are supposed to survive between requests in production), so tests replace
    them rather than reaching into private cache state.
    """
    from app.api import search as search_api
    from app.services.alphafold import AlphaFoldClient
    from app.services.rcsb import RCSBClient
    from app.services.uniprot import UniProtClient

    uniprot = UniProtClient()
    monkeypatch.setitem(search_api._CLIENTS, "rcsb", RCSBClient())
    monkeypatch.setitem(search_api._CLIENTS, "alphafold", AlphaFoldClient(uniprot=uniprot))
    monkeypatch.setitem(search_api._CLIENTS, "uniprot", uniprot)
