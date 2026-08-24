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


@pytest.fixture(autouse=True)
def fresh_complex_portal_client(monkeypatch):
    """Per-test: a fresh Complex Portal client, so its TTL cache never leaks.

    Its singleton lives in `services/complexes` rather than `api/search`'s
    `_CLIENTS` registry — Complex Portal is not a search source — so it needs
    its own swap.
    """
    from app.services import complexes as complexes_service

    monkeypatch.setattr(
        complexes_service, "_CLIENT", complexes_service.ComplexPortalClient()
    )


@pytest.fixture(autouse=True)
def fresh_pae_cache():
    """Per-test: an empty binned-PAE cache.

    A1's cache lives in `services/confidence` rather than on a client, because
    what it stores is the *binned* matrix (see the module docstring). It is
    module-level in production for the same reason the client caches are, so a
    test that fetches P01308 twice would otherwise see the second call served
    from the first test's entry and never reach the mocked transport.
    """
    from app.services import confidence

    confidence.clear_pae_cache()
    yield
    confidence.clear_pae_cache()


@pytest.fixture(autouse=True)
def fresh_blast_registry(monkeypatch):
    """Per-test: a clean BLAST job registry with the upstream poll throttle off.

    The throttle (`MIN_UPSTREAM_POLL_SECONDS`) is a real production behaviour,
    so it gets its own dedicated test rather than being switched off globally
    and forgotten — every *other* test wants consecutive polls to actually
    reach the mocked transport.
    """
    from app.services import blast_jobs

    monkeypatch.setattr(
        blast_jobs,
        "_REGISTRY",
        blast_jobs.BlastJobRegistry(min_upstream_poll_seconds=0.0),
    )


@pytest.fixture(autouse=True)
def default_blast_contact_email(monkeypatch):
    """Pin the BLAST contact address so a developer's own env cannot leak into
    an assertion — or into a recorded request body."""
    monkeypatch.delenv("BLAST_CONTACT_EMAIL", raising=False)
