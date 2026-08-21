"""Unit tests for the analytics service + endpoint round-trip."""
from __future__ import annotations

from pathlib import Path

from Bio.PDB import MMCIFParser, PDBParser
from fastapi.testclient import TestClient

from app.main import app
from app.services import analytics

PDB_PATH = Path(__file__).resolve().parents[1] / "app" / "static" / "1CRN.pdb"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# `1CRN_ss.cif` is `1CRN.cif` (coordinates only) with the mmCIF spelling of the
# four HELIX/SHEET records real 1CRN carries — `_struct_conf` for the two
# helices, `_struct_sheet_range` for the two strands — spliced in ahead of the
# `_atom_site` loop. Both numbering schemes (`label_*` and `auth_*`) are present,
# as in an RCSB-served file. Built offline; nothing here is downloaded.
CIF_WITH_SS = FIXTURES / "1CRN_ss.cif"
# Same coordinates, no SS categories at all — the genuinely-unannotated case.
CIF_WITHOUT_SS = FIXTURES / "1CRN.cif"
# A PDB with no HELIX/SHEET records, like an AlphaFold prediction.
PDB_WITHOUT_SS = FIXTURES / "parity_multichain.pdb"

# Crambin's SS split, pinned so any change to the counting is loud:
# helices 7-19 (13 residues) + 23-30 (8) = 21/46; strands 1-4 (4) + 32-35 (4) = 8/46.
CRAMBIN_SS = {"helix": 0.4565, "sheet": 0.1739, "coil": 0.3696}

client = TestClient(app)

# 1CRN sequence (46 residues)
CRAMBIN_SEQ = "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN"


def test_molecular_weight_crambin() -> None:
    # Crambin published MW ~4736 Da
    mw = analytics.molecular_weight(CRAMBIN_SEQ)
    assert 4700 <= mw <= 4770, f"Expected crambin MW ~4736, got {mw}"


def test_molecular_weight_empty() -> None:
    assert analytics.molecular_weight("") == 0.0


def test_molecular_weight_skips_unknown() -> None:
    # X residues are skipped, so adding them should not change MW.
    base = analytics.molecular_weight("ACDEF")
    with_x = analytics.molecular_weight("ACDXEF")
    assert with_x == base


def test_composition_returns_20_entries() -> None:
    comp = analytics.composition(CRAMBIN_SEQ)
    assert len(comp) == 20
    aas = {e["aa"] for e in comp}
    assert aas == set("ACDEFGHIKLMNPQRSTVWY")


def test_composition_counts_crambin() -> None:
    comp = analytics.composition(CRAMBIN_SEQ)
    by_aa = {e["aa"]: e["count"] for e in comp}
    # 1CRN has 6 cysteines (well-known disulfide-rich protein).
    assert by_aa["C"] == 6
    # 1CRN has multiple threonines.
    assert by_aa["T"] >= 4
    # Percent sums to ~100 (within rounding).
    pct_sum = sum(e["percent"] for e in comp)
    assert 99.0 <= pct_sum <= 100.5


def test_composition_percent_zero_for_empty() -> None:
    comp = analytics.composition("")
    assert all(e["percent"] == 0.0 and e["count"] == 0 for e in comp)


def test_hydrophobicity_window_9_crambin() -> None:
    profile = analytics.hydrophobicity_profile(CRAMBIN_SEQ, window=9)
    # 46 residues, window 9 -> 46 - 9 + 1 = 38 windows.
    assert len(profile) == 38
    # All values within Kyte-Doolittle range.
    assert all(-4.5 <= v <= 4.5 for v in profile)


def test_hydrophobicity_empty_seq() -> None:
    assert analytics.hydrophobicity_profile("", 9) == []


def test_hydrophobicity_short_seq() -> None:
    # Sequence shorter than window.
    assert analytics.hydrophobicity_profile("ACGT", 9) == []


def test_hydrophobicity_window_1() -> None:
    # Window 1 should just be the per-residue KD scale.
    profile = analytics.hydrophobicity_profile("AAA", window=1)
    assert profile == [1.8, 1.8, 1.8]


def test_property_distribution_crambin() -> None:
    props = analytics.property_distribution(CRAMBIN_SEQ)
    # 1CRN: 6 cysteines, several hydrophobic.
    assert props["cysteine"] == 6
    assert props["hydrophobic"] > 10
    # Categories may overlap (aromatic intentionally also counts as hydrophobic).
    assert all(v >= 0 for v in props.values())


def test_property_distribution_keys() -> None:
    props = analytics.property_distribution("A")
    expected_keys = {
        "hydrophobic",
        "polar",
        "charged_positive",
        "charged_negative",
        "aromatic",
        "cysteine",
    }
    assert set(props.keys()) == expected_keys


def test_secondary_structure_sums_to_one() -> None:
    # Need a real structure; parse 1CRN.
    structure = PDBParser(QUIET=True).get_structure("1crn", str(PDB_PATH))
    ss = analytics.secondary_structure_percentages(structure, pdb_path=PDB_PATH)
    total = ss["helix"] + ss["sheet"] + ss["coil"]
    assert 0.99 <= total <= 1.01, f"SS fractions should sum to ~1.0, got {total}"
    # 1CRN has helices (residues 7-19 + 23-30); helix fraction should be > 0.1.
    assert ss["helix"] > 0.1


def test_secondary_structure_all_coil_when_no_records() -> None:
    """With no HELIX/SHEET records and no file path, everything is coil."""
    structure = PDBParser(QUIET=True).get_structure("1crn", str(PDB_PATH))
    ss = analytics.secondary_structure_percentages(structure)
    # Without the file path the BioPython header has helix=None / sheet=None,
    # so the function should report 100% coil.
    assert ss == {"helix": 0.0, "sheet": 0.0, "coil": 1.0}


def test_secondary_structure_pdb_percentages_are_pinned() -> None:
    """The legacy PDB path must keep producing exactly today's numbers."""
    structure = PDBParser(QUIET=True).get_structure("1crn", str(PDB_PATH))
    result = analytics.secondary_structure(structure, path=PDB_PATH)
    assert result.helix == CRAMBIN_SS["helix"]
    assert result.sheet == CRAMBIN_SS["sheet"]
    assert result.coil == CRAMBIN_SS["coil"]
    assert result.available is True


def test_secondary_structure_from_mmcif_struct_conf() -> None:
    """mmCIF `_struct_conf` / `_struct_sheet_range` yield real helix and sheet.

    Regression guard for the format bug: an mmCIF has no `HELIX `/`SHEET ` text
    records, so scanning for them reported every RCSB import as 100% coil.
    """
    structure = MMCIFParser(QUIET=True).get_structure("1crn", str(CIF_WITH_SS))
    result = analytics.secondary_structure(structure, path=CIF_WITH_SS)
    assert result.helix > 0.0, "mmCIF helices must be counted, not read as coil"
    assert result.sheet > 0.0, "mmCIF strands must be counted, not read as coil"
    assert result.helix == CRAMBIN_SS["helix"]
    assert result.sheet == CRAMBIN_SS["sheet"]
    assert result.coil == CRAMBIN_SS["coil"]
    assert result.available is True


def test_secondary_structure_mmcif_matches_pdb_for_same_entry() -> None:
    """Same protein, same annotations, two formats -> identical percentages."""
    from_pdb = analytics.secondary_structure_percentages(
        PDBParser(QUIET=True).get_structure("1crn", str(PDB_PATH)), pdb_path=PDB_PATH
    )
    from_cif = analytics.secondary_structure_percentages(
        MMCIFParser(QUIET=True).get_structure("1crn", str(CIF_WITH_SS)),
        pdb_path=CIF_WITH_SS,
    )
    assert from_cif == from_pdb


def test_secondary_structure_percentages_view_returns_only_fractions() -> None:
    """The float-only view keeps its three-key shape for existing callers."""
    structure = MMCIFParser(QUIET=True).get_structure("1crn", str(CIF_WITH_SS))
    ss = analytics.secondary_structure_percentages(structure, pdb_path=CIF_WITH_SS)
    assert set(ss) == {"helix", "sheet", "coil"}


def test_secondary_structure_unavailable_for_mmcif_without_categories() -> None:
    """An mmCIF that annotates no SS is reported as unavailable, not as coil."""
    structure = MMCIFParser(QUIET=True).get_structure("1crn", str(CIF_WITHOUT_SS))
    result = analytics.secondary_structure(structure, path=CIF_WITHOUT_SS)
    assert result.available is False
    assert (result.helix, result.sheet, result.coil) == (0.0, 0.0, 1.0)


def test_secondary_structure_unavailable_for_pdb_without_records() -> None:
    """A PDB with no HELIX/SHEET records (e.g. AlphaFold) is unavailable too."""
    structure = PDBParser(QUIET=True).get_structure("multi", str(PDB_WITHOUT_SS))
    result = analytics.secondary_structure(structure, path=PDB_WITHOUT_SS)
    assert result.available is False
    assert (result.helix, result.sheet, result.coil) == (0.0, 0.0, 1.0)


def test_analytics_endpoint_reports_mmcif_secondary_structure() -> None:
    """The flagship import flow: an mmCIF upload must not render as all coil."""
    with CIF_WITH_SS.open("rb") as f:
        r = client.post(
            "/api/proteins/upload",
            files={"file": ("1crn_ss.cif", f, "chemical/x-mmcif")},
        )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]

    r2 = client.get(f"/api/proteins/{uid}/analytics")
    assert r2.status_code == 200, r2.text
    ss = r2.json()["secondary_structure"]
    assert ss["helix"] == CRAMBIN_SS["helix"]
    assert ss["sheet"] == CRAMBIN_SS["sheet"]
    assert ss["coil"] == CRAMBIN_SS["coil"]
    assert ss["available"] is True


def test_analytics_endpoint_flags_missing_secondary_structure() -> None:
    """An unannotated structure still returns coil=1.0, but flagged as such."""
    with CIF_WITHOUT_SS.open("rb") as f:
        r = client.post(
            "/api/proteins/upload",
            files={"file": ("1crn.cif", f, "chemical/x-mmcif")},
        )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]

    r2 = client.get(f"/api/proteins/{uid}/analytics")
    assert r2.status_code == 200, r2.text
    ss = r2.json()["secondary_structure"]
    assert ss["available"] is False
    assert ss["coil"] == 1.0


def test_analytics_endpoint_round_trip() -> None:
    """Upload 1CRN, then GET /analytics."""
    with PDB_PATH.open("rb") as f:
        r = client.post(
            "/api/proteins/upload",
            files={"file": ("1crn.pdb", f, "chemical/x-pdb")},
        )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]

    r2 = client.get(f"/api/proteins/{uid}/analytics")
    assert r2.status_code == 200, r2.text
    body = r2.json()

    # Top-level shape.
    assert body["id"] == uid
    assert 4700 <= body["molecular_weight"] <= 4770
    assert body["residue_count"] == 46
    assert body["chain_count"] == 1

    # Composition.
    assert len(body["composition"]) == 20
    by_aa = {e["aa"]: e["count"] for e in body["composition"]}
    assert by_aa["C"] == 6

    # SS percentages.
    ss = body["secondary_structure"]
    assert 0.99 <= ss["helix"] + ss["sheet"] + ss["coil"] <= 1.01
    assert ss["helix"] > 0.1

    # Hydrophobicity (window 9 on chain A, 46 residues -> 38 values).
    hp = body["hydrophobicity"]
    assert hp["chain_id"] == "A"
    assert hp["window"] == 9
    assert len(hp["values"]) == 38

    # Property distribution.
    props = body["property_distribution"]
    assert props["cysteine"] == 6

    # Chain lengths.
    assert body["chain_lengths"] == [{"chain_id": "A", "length": 46}]


def test_analytics_endpoint_404_for_unknown() -> None:
    r = client.get("/api/proteins/" + ("0" * 32) + "/analytics")
    assert r.status_code == 404


def test_analytics_endpoint_404_for_invalid_uid() -> None:
    r = client.get("/api/proteins/not-a-uid/analytics")
    assert r.status_code == 404
