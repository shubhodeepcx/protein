"""Fan-out behaviour of GET /api/search.

The three clients are replaced with in-process fakes so these tests exercise
the router's own contract — gather, dedupe, per-source failure isolation — and
never touch HTTP. Client-level HTTP behaviour is covered by
`test_external_clients.py`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import search as search_api
from app.main import app
from app.models.search import SearchResult

client = TestClient(app)


class FakeClient:
    """Stand-in with the same three-coroutine interface as the real clients."""

    def __init__(self, results: list[SearchResult] | None = None, error: Exception | None = None):
        self._results = results or []
        self._error = error
        self.queries: list[str] = []

    async def search(self, query: str) -> list[SearchResult]:
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return list(self._results)

    async def fetch_metadata(self, protein_id: str) -> dict:  # pragma: no cover - unused
        raise NotImplementedError

    async def download_structure(self, protein_id: str) -> tuple[bytes, str]:
        raise NotImplementedError


def hit(source: str, source_id: str, title: str = "Some protein") -> SearchResult:
    return SearchResult(source=source, source_id=source_id, title=title)  # type: ignore[arg-type]


@pytest.fixture
def fakes(monkeypatch) -> dict[str, FakeClient]:
    """Install fake clients and hand them back for per-test configuration."""
    installed = {
        "rcsb": FakeClient([hit("rcsb", "1CRN", "Crambin")]),
        "alphafold": FakeClient([hit("alphafold", "P69905", "Hemoglobin subunit alpha")]),
        "uniprot": FakeClient([hit("uniprot", "P01308", "Insulin")]),
    }
    for name, fake in installed.items():
        monkeypatch.setitem(search_api._CLIENTS, name, fake)
    return installed


def test_search_all_sources_merges_results(fakes) -> None:
    r = client.get("/api/search", params={"q": "insulin"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["query"] == "insulin"
    assert body["failed_sources"] == []
    assert {(h["source"], h["source_id"]) for h in body["results"]} == {
        ("rcsb", "1CRN"),
        ("alphafold", "P69905"),
        ("uniprot", "P01308"),
    }
    for fake in fakes.values():
        assert fake.queries == ["insulin"]


def test_search_reports_failed_source_without_failing_the_request(fakes, monkeypatch) -> None:
    monkeypatch.setitem(
        search_api._CLIENTS, "rcsb", FakeClient(error=RuntimeError("RCSB search exploded"))
    )

    r = client.get("/api/search", params={"q": "insulin"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["failed_sources"] == ["rcsb"]
    # The two healthy sources still returned their hits.
    assert {h["source"] for h in body["results"]} == {"alphafold", "uniprot"}


def test_search_dedupes_by_source_and_source_id(fakes, monkeypatch) -> None:
    monkeypatch.setitem(
        search_api._CLIENTS,
        "rcsb",
        FakeClient([hit("rcsb", "1CRN"), hit("rcsb", "1crn"), hit("rcsb", "4HHB")]),
    )

    r = client.get("/api/search", params={"q": "insulin"})

    assert r.status_code == 200, r.text
    rcsb_ids = [h["source_id"] for h in r.json()["results"] if h["source"] == "rcsb"]
    assert rcsb_ids == ["1CRN", "4HHB"]


def test_search_source_filter_queries_only_that_source(fakes) -> None:
    r = client.get("/api/search", params={"q": "crambin", "source": "rcsb"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert {h["source"] for h in body["results"]} == {"rcsb"}
    assert fakes["rcsb"].queries == ["crambin"]
    assert fakes["alphafold"].queries == []
    assert fakes["uniprot"].queries == []


def test_search_all_sources_failing_returns_200_with_every_source_named(monkeypatch) -> None:
    for name in ("rcsb", "alphafold", "uniprot"):
        monkeypatch.setitem(search_api._CLIENTS, name, FakeClient(error=RuntimeError("down")))

    r = client.get("/api/search", params={"q": "insulin"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["results"] == []
    assert sorted(body["failed_sources"]) == ["alphafold", "rcsb", "uniprot"]


@pytest.mark.parametrize("q", ["", "   ", "\t\n"])
def test_search_rejects_blank_query(fakes, q: str) -> None:
    r = client.get("/api/search", params={"q": q})
    assert r.status_code == 400, r.text
    assert "empty" in r.json()["detail"].lower()


def test_search_requires_the_q_parameter(fakes) -> None:
    assert client.get("/api/search").status_code == 422


def test_search_rejects_an_overlong_query(fakes) -> None:
    r = client.get("/api/search", params={"q": "x" * 500})
    assert r.status_code == 400
    assert "too long" in r.json()["detail"].lower()


def test_search_rejects_an_unknown_source(fakes) -> None:
    assert client.get("/api/search", params={"q": "x", "source": "pdbe"}).status_code == 422
