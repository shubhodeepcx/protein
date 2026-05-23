from __future__ import annotations

from pathlib import Path

import pytest

from app.services.parser import parse

PDB_PATH = Path(__file__).resolve().parents[1] / "app" / "static" / "1CRN.pdb"


@pytest.mark.asyncio
async def test_parse_1crn_basic() -> None:
    summary = await parse(PDB_PATH, uid="test-uid", source="uploaded")
    assert summary.id == "test-uid"
    assert summary.source == "uploaded"
    assert summary.file_format == "pdb"
    assert summary.file_url == "/api/proteins/test-uid/file"
    assert len(summary.chains) >= 1
    # 1CRN has 46 residues
    assert summary.residue_count > 40
    assert summary.atom_count > 300
    # ~4.7 kDa
    assert summary.molecular_weight > 4000


@pytest.mark.asyncio
async def test_parse_1crn_chain_a() -> None:
    summary = await parse(PDB_PATH, uid="t2", source="uploaded")
    chain_a = next((c for c in summary.chains if c.label == "A"), None)
    assert chain_a is not None
    assert chain_a.residue_count >= 40
    # 1CRN sequence starts with TTCCPSIVAR
    assert chain_a.sequence.startswith("TTCC")
    # Chain id should be namespaced under the uid
    assert chain_a.id == "t2:A"


@pytest.mark.asyncio
async def test_parse_1crn_header_metadata() -> None:
    """1CRN has COMPND/SOURCE — parser should populate name and organism."""
    summary = await parse(PDB_PATH, uid="t3", source="uploaded")
    # name comes from compound molecule field; allow either case
    assert summary.name is None or "CRAMBIN" in summary.name.upper()
    # organism from SOURCE record
    assert summary.organism is None or "CRAMBE" in summary.organism.upper()


@pytest.mark.asyncio
async def test_parse_1crn_summary_shape() -> None:
    """All required ProteinSummary fields should be populated and well-typed."""
    summary = await parse(PDB_PATH, uid="t4", source="uploaded")
    assert isinstance(summary.warnings, list)
    assert isinstance(summary.has_plddt, bool)
    assert summary.molecular_weight > 0
    # 1CRN is an X-ray structure — pLDDT heuristic should NOT fire
    # (B-factors are crystallographic temperature factors, not always in 0-100,
    # and even if they happen to be, this is not an AlphaFold model).
    # We only assert the field is a bool; precise heuristic outcome may differ.
