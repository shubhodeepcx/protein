from __future__ import annotations

from pathlib import Path

from app.services.parser import (
    _MMCIF_ORGANISM_MAX_CHARS,
    _extract_mmcif_organism,
    parse,
)

PDB_PATH = Path(__file__).resolve().parents[1] / "app" / "static" / "1CRN.pdb"


def test_parse_1crn_basic() -> None:
    summary = parse(PDB_PATH, uid="test-uid", source="uploaded")
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


def test_parse_1crn_chain_a() -> None:
    summary = parse(PDB_PATH, uid="t2", source="uploaded")
    chain_a = next((c for c in summary.chains if c.label == "A"), None)
    assert chain_a is not None
    assert chain_a.residue_count >= 40
    # 1CRN sequence starts with TTCCPSIVAR
    assert chain_a.sequence.startswith("TTCC")
    # Chain id should be namespaced under the uid
    assert chain_a.id == "t2:A"


def test_parse_1crn_header_metadata() -> None:
    summary = parse(PDB_PATH, uid="t3", source="uploaded")
    # 1CRN has COMPND/SOURCE records; parser should extract them.
    # If both are None, the header extraction path is broken.
    assert summary.name is not None, "Expected name from 1CRN COMPND record"
    assert "CRAMBIN" in summary.name.upper()
    assert summary.organism is not None, "Expected organism from 1CRN SOURCE record"
    assert "CRAMBE" in summary.organism.upper()


def test_parse_1crn_summary_shape() -> None:
    """All required ProteinSummary fields should be populated and well-typed."""
    summary = parse(PDB_PATH, uid="t4", source="uploaded")
    assert isinstance(summary.warnings, list)
    assert isinstance(summary.has_plddt, bool)
    assert summary.molecular_weight > 0
    # 1CRN is an X-ray structure — pLDDT heuristic should NOT fire
    # (B-factors are crystallographic temperature factors, not always in 0-100,
    # and even if they happen to be, this is not an AlphaFold model).
    # We only assert the field is a bool; precise heuristic outcome may differ.


# ---------------------------------------------------------------- mmCIF header
#
# BioPython's MMCIFParser builds `structure.header` from six keys only — name,
# head, idcode, deposition_date, structure_method, resolution — with no `source`
# entry at all. `_extract_header_strings` reads PDB-header keys (`compound`,
# `source`), so before the mmCIF fallback existed every mmCIF parsed to
# `organism=None`. Every RCSB import is an mmCIF, so that was every RCSB import.

CIF_WITH_NAT_SOURCE = Path(__file__).resolve().parent / "fixtures" / "1CRN_header.cif"
CIF_WITH_GEN_SOURCE = Path(__file__).resolve().parent / "fixtures" / "entity_src_gen.cif"
CIF_WITHOUT_SOURCE = Path(__file__).resolve().parent / "fixtures" / "1CRN.cif"


def test_parse_mmcif_reads_organism_from_entity_src_nat() -> None:
    """An isolated-from-nature entry (what real 1CRN carries)."""
    summary = parse(CIF_WITH_NAT_SOURCE, uid="cif1", source="rcsb", source_id="1CRN")
    assert summary.file_format == "mmcif"
    assert summary.organism is not None, (
        "mmCIF organism came back None — the _entity_src_nat fallback is not firing"
    )
    assert "CRAMBE" in summary.organism.upper()


def test_parse_mmcif_reads_organism_from_entity_src_gen() -> None:
    """A recombinant entry: organism is the GENE source, not the host organism."""
    summary = parse(CIF_WITH_GEN_SOURCE, uid="cif2", source="rcsb", source_id="TEST")
    assert summary.organism == "Homo sapiens"
    # The host (E. coli) must never win — it is where the protein was expressed,
    # not what the protein is from.
    assert "coli" not in (summary.organism or "").lower()


def test_parse_mmcif_still_reads_name_from_the_biopython_header() -> None:
    """The organism fallback must not disturb the `_struct.title` -> name path."""
    summary = parse(CIF_WITH_NAT_SOURCE, uid="cif3", source="rcsb", source_id="1CRN")
    assert summary.name is not None
    assert "WATER STRUCTURE" in summary.name.upper()


def test_parse_mmcif_without_any_source_category_leaves_organism_none() -> None:
    """No source category anywhere -> None, not a `?`/`.` mmCIF null token."""
    summary = parse(CIF_WITHOUT_SOURCE, uid="cif4", source="rcsb", source_id="1CRN")
    assert summary.organism is None
    # ...and the rest of the parse is unaffected.
    assert summary.residue_count == 46


def test_parse_pdb_organism_path_is_unchanged_by_the_mmcif_fallback() -> None:
    """The mmCIF branch is gated on format: a PDB must still use its SOURCE record."""
    summary = parse(PDB_PATH, uid="cif5", source="uploaded")
    assert summary.file_format == "pdb"
    assert summary.organism is not None
    assert "CRAMBE" in summary.organism.upper()


def test_parse_mmcif_skips_null_tokens_and_keeps_walking_the_chain() -> None:
    """`?` and `.` are mmCIF nulls, not organism names.

    Fixture has `?` in `_entity_src_gen`, `.` in `_entity_src_nat`, and the real
    organism in `_pdbx_entity_src_syn`. A reader that trusts the first non-empty
    string renders "Organism: ?".
    """
    path = Path(__file__).resolve().parent / "fixtures" / "null_source_tokens.cif"
    summary = parse(path, uid="cif6", source="rcsb", source_id="TEST")
    assert summary.organism == "Gallus gallus"


# ------------------------------------------------------- multi-entity organisms
#
# `_entity_src_gen` is a looped category: one row per entity. Taking the first
# row reports a hetero-complex as if every chain came from one species — a
# human/yeast complex renders as "Homo sapiens". `ProteinSummary.organism` stays
# a single string (the UI renders it as one line), so the distinct names are
# joined instead, and a single-organism file must be untouched by that.

CIF_MULTI_ENTITY = Path(__file__).resolve().parent / "fixtures" / "multi_entity_organisms.cif"
CIF_MULTI_ENTITY_SAME = (
    Path(__file__).resolve().parent / "fixtures" / "multi_entity_same_organism.cif"
)


def test_parse_mmcif_reports_every_organism_of_a_multi_entity_file() -> None:
    """Two entities, two different gene sources — both must be reported."""
    summary = parse(CIF_MULTI_ENTITY, uid="cif7", source="rcsb", source_id="TEST")
    assert summary.organism is not None
    # Both names present, in file order, joined into the one line the UI renders.
    assert summary.organism == "Homo sapiens, Saccharomyces cerevisiae", (
        "multi-entity mmCIF reported only one organism — the other entity was dropped"
    )
    # Reading every row must not start letting the expression host in: E. coli is
    # the `pdbx_host_org_scientific_name` on both rows.
    assert "coli" not in summary.organism.lower()
    # The structure itself still parses as before.
    assert {c.label for c in summary.chains} == {"A", "B"}


def test_parse_mmcif_multi_entity_with_one_organism_renders_as_a_plain_name() -> None:
    """Same species on every entity -> exactly that name, as before the join.

    The fixture spells it three ways ("Homo sapiens" / "HOMO SAPIENS" /
    "homo sapiens") across two categories, so this also pins the
    case-insensitive dedupe and the first-seen spelling winning.
    """
    summary = parse(CIF_MULTI_ENTITY_SAME, uid="cif8", source="rcsb", source_id="TEST")
    assert summary.organism == "Homo sapiens"
    # No trailing separator, no cap tail, no duplicate.
    assert "," not in summary.organism
    assert "more" not in summary.organism


def test_mmcif_organism_join_is_capped_and_admits_that_it_capped() -> None:
    """A 20-entity assembly must not produce an absurd line — or lie about it.

    Whatever does not fit is *counted*, never silently dropped: the names that
    are shown plus the "and N more" tally must add back up to the input.
    """
    names = [f"Organism species number {i}" for i in range(1, 21)]
    rendered = _extract_mmcif_organism({"_entity_src_gen.pdbx_gene_src_scientific_name": names})
    assert rendered is not None

    head, _, tail = rendered.partition(" and ")
    assert tail.endswith(" more"), f"capped organism line hid the overflow: {rendered!r}"
    shown = head.split(", ")
    hidden = int(tail[: -len(" more")])
    assert len(shown) + hidden == len(names)
    assert shown[0] == names[0]
    # Every shown name is whole — a truncated species name would be a made-up one.
    assert all(name in names for name in shown)
    # The names themselves stay inside the budget; the tail is a short constant.
    assert len(head) <= _MMCIF_ORGANISM_MAX_CHARS


def test_mmcif_organism_never_truncates_a_single_over_budget_name() -> None:
    """One absurdly long name is reported whole, not sliced to fit the budget."""
    long_name = "Candidatus " + "Longissimus" * 20
    assert len(long_name) > _MMCIF_ORGANISM_MAX_CHARS
    rendered = _extract_mmcif_organism(
        {"_entity_src_nat.pdbx_organism_scientific": [long_name, "Homo sapiens"]}
    )
    assert rendered == f"{long_name} and 1 more"
