"""Unit tests for `services/ingest.parse_and_register`.

This is the store->parse->register->unlink flow the upload and import routers
used to duplicate (each with its own copy of the try/except/unlink block).
`test_upload.py` and `test_import_api.py` exercise it end to end through the
HTTP routes; these tests pin the shared function itself, including the
unlink-on-failure behaviour neither route-level test previously asserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.protein import ChainInfo, ProteinSummary
from app.services import ingest, registry
from app.services.ingest import EmptyStructureError, StructureParseFailed


def _make_summary(chains: list[ChainInfo]) -> ProteinSummary:
    return ProteinSummary(
        id="ingest-test",
        source="uploaded",
        source_id=None,
        name=None,
        organism=None,
        file_url="/api/proteins/ingest-test/file",
        file_format="pdb",
        chains=chains,
        residue_count=0,
        atom_count=0,
        molecular_weight=0.0,
        has_plddt=False,
        warnings=[],
    )


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def stored_file(tmp_path: Path) -> Path:
    path = tmp_path / "ingest-test.pdb"
    path.write_bytes(b"not a real structure, content does not matter here")
    return path


async def test_parse_and_register_registers_and_returns_the_summary(
    monkeypatch: pytest.MonkeyPatch, stored_file: Path
) -> None:
    summary = _make_summary(
        [ChainInfo(id="ingest-test:A", label="A", sequence="AC", residue_count=2)]
    )
    monkeypatch.setattr(ingest.parser, "parse", lambda *a, **kw: summary)

    result = await ingest.parse_and_register(stored_file, "ingest-test", source="uploaded")

    assert result is summary
    assert registry.get("ingest-test") is summary
    assert stored_file.exists(), "a successful parse must not delete the stored file"


async def test_parse_and_register_unlinks_and_raises_on_parser_exception(
    monkeypatch: pytest.MonkeyPatch, stored_file: Path
) -> None:
    def _boom(*_a: object, **_kw: object) -> None:
        raise ValueError("garbage content")

    monkeypatch.setattr(ingest.parser, "parse", _boom)

    with pytest.raises(StructureParseFailed):
        await ingest.parse_and_register(stored_file, "ingest-test", source="uploaded")

    assert not stored_file.exists(), "a parse failure must clean up the stored file"
    assert registry.get("ingest-test") is None


async def test_parse_and_register_unlinks_and_raises_on_empty_chains(
    monkeypatch: pytest.MonkeyPatch, stored_file: Path
) -> None:
    summary = _make_summary([])
    monkeypatch.setattr(ingest.parser, "parse", lambda *a, **kw: summary)

    with pytest.raises(EmptyStructureError):
        await ingest.parse_and_register(stored_file, "ingest-test", source="uploaded")

    assert not stored_file.exists(), "an empty-chain parse must clean up the stored file"
    assert registry.get("ingest-test") is None


async def test_parse_and_register_survives_an_already_missing_file(
    monkeypatch: pytest.MonkeyPatch, stored_file: Path
) -> None:
    """unlink uses missing_ok=True — a second cleanup attempt must not raise."""

    def _boom(*_a: object, **_kw: object) -> None:
        stored_file.unlink()  # simulate another process/cleanup winning the race
        raise ValueError("garbage content")

    monkeypatch.setattr(ingest.parser, "parse", _boom)

    with pytest.raises(StructureParseFailed):
        await ingest.parse_and_register(stored_file, "ingest-test", source="uploaded")
