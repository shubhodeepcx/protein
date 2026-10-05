"""Compounds: the non-protein components of a structure.

Most cases run against `compounds_complex.pdb`, built by
`fixtures/make_compounds_fixture.py` from real 1CRN backbone geometry. Its
docstring lists what each group is placed to test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.proteins import parse_structure_for_analytics
from app.main import app
from app.models.compounds import CompoundsResponse
from app.services import analytics, compounds, functional, registry
from app.services.parser import is_nucleic_acid_chain, parse
from app.storage import local as storage
from tests.helpers import FIXTURES

client = TestClient(app)

COMPLEX = FIXTURES / "compounds_complex.pdb"

DNA_ONLY = """\
ATOM      1  P    DA B   1       0.000   0.000   0.000  1.00  0.00           P
ATOM      2  C1'  DA B   1       1.000   0.000   0.000  1.00  0.00           C
ATOM      3  P    DT B   2       4.000   0.000   0.000  1.00  0.00           P
END
"""


def build(path: Path) -> CompoundsResponse:
    summary = parse(path, "u")
    return compounds.build_compounds(
        "u", summary, parse_structure_for_analytics(path), compounds.read_component_info(path)
    )


@pytest.fixture(scope="module")
def complex_compounds() -> CompoundsResponse:
    return build(COMPLEX)


def group(response: CompoundsResponse, code: str):
    matches = [g for g in response.groups if g.code == code]
    assert len(matches) == 1, f"expected one {code} group, got {len(matches)}"
    return matches[0]


# ------------------------------------------------------------ parser seam


class TestNucleicAcidChains:
    def test_dna_chain_is_not_a_protein_chain(self) -> None:
        summary = parse(COMPLEX, "u")
        assert [c.label for c in summary.chains] == ["A"]
        assert summary.nucleic_acid_chains == ["B"]
        assert any("Nucleic-acid chains" in w and "B" in w for w in summary.warnings)

    def test_dna_no_longer_reported_as_nonstandard_protein_residues(self) -> None:
        # The bug this fixes: DA/DC/DG used to land in `chains` as 'X'.
        summary = parse(COMPLEX, "u")
        assert not any("replaced with 'X'" in w for w in summary.warnings)
        assert "X" not in summary.chains[0].sequence

    def test_protein_ordinals_skip_the_modified_residue(self) -> None:
        # SER 6 is HETATM SEP, so A:6 is ILE 7 — unchanged from before.
        assert parse(COMPLEX, "u").chains[0].sequence == "TTCCPIVAR"

    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            (["DA", "DT"], True),
            (["A", "U", "G"], True),
            ([" DC", "DG "], True),
            (["DA", "ALA"], False),  # any amino acid keeps it a protein chain
            (["UNK", "UNK"], False),  # poly-UNK cryo-EM model stays protein
            ([], False),
        ],
    )
    def test_is_nucleic_acid_chain(self, names: list[str], expected: bool) -> None:
        assert is_nucleic_acid_chain(names) is expected

    def test_functional_reread_accepts_a_structure_with_dna(self) -> None:
        summary = parse(COMPLEX, "u")
        chains = functional.read_chain_residues(parse_structure_for_analytics(COMPLEX), summary)
        assert [c.label for c in chains] == ["A"]

    def test_secondary_structure_denominator_excludes_dna(self) -> None:
        structure = parse_structure_for_analytics(COMPLEX)
        assert analytics._count_polymer_residues(structure) == 9


# ------------------------------------------------------------ classification


class TestCategories:
    def test_every_category_lands_where_it_is_placed(
        self, complex_compounds: CompoundsResponse
    ) -> None:
        assert {g.code: g.category for g in complex_compounds.groups} == {
            "SEP": "modified_residue",
            "ZN": "ion",
            "GLU": "free_amino_acid",
            "HEM": "cofactor",
            "SO4": "additive",
            "LIG": "ligand",
        }

    def test_waters_are_counted_not_listed(self, complex_compounds: CompoundsResponse) -> None:
        assert complex_compounds.water_count == 2
        assert "HOH" not in {g.code for g in complex_compounds.groups}

    def test_groups_follow_category_order(self, complex_compounds: CompoundsResponse) -> None:
        order = [compounds.CATEGORY_ORDER.index(g.category) for g in complex_compounds.groups]
        assert order == sorted(order)

    @pytest.mark.parametrize(
        ("code", "kwargs", "expected"),
        [
            ("NAG", {}, "carbohydrate"),
            ("XYZ", {"chem_type": "D-saccharide, beta linking"}, "carbohydrate"),
            ("XX1", {"heavy_elements": ["ZN"]}, "ion"),
            ("XX2", {"heavy_elements": ["C"]}, "ligand"),
            ("ATP", {}, "cofactor"),
            ("GOL", {}, "additive"),
            ("MSE", {}, "free_amino_acid"),
            ("MSE", {"in_polymer": True}, "modified_residue"),
            ("XX3", {"chem_type": "L-peptide linking"}, "free_amino_acid"),
            ("XX4", {"has_backbone": True}, "free_amino_acid"),
            ("STI", {}, "ligand"),
        ],
    )
    def test_classify(self, code: str, kwargs: dict, expected: str) -> None:
        args = {"heavy_elements": ["C", "C"], "in_polymer": False, "has_backbone": False,
                "chem_type": None, **kwargs}
        assert compounds.classify(code, **args) == expected


# ------------------------------------------------------------ in-chain vs free


class TestPeptideBondRule:
    def test_modified_residue_is_in_chain_and_has_no_contacts(
        self, complex_compounds: CompoundsResponse
    ) -> None:
        sep = group(complex_compounds, "SEP")
        assert sep.parent_residue == "S"
        assert sep.instances[0].contacts == []

    def test_free_amino_acid_is_reported_with_its_contacts(
        self, complex_compounds: CompoundsResponse
    ) -> None:
        # The case A5's backbone rule skipped: a whole amino acid, not bonded.
        glu = group(complex_compounds, "GLU")
        assert glu.parent_residue == "E"
        keys = [c.key for c in glu.instances[0].contacts]
        assert "A:6" in keys  # ILE 7, whose CB it was placed against
        assert all(c.min_distance <= complex_compounds.contact_cutoff for c in glu.instances[0].contacts)


# ------------------------------------------------------------ contacts


class TestContacts:
    def test_ion_contacts_its_cysteine(self, complex_compounds: CompoundsResponse) -> None:
        zn = group(complex_compounds, "ZN").instances[0]
        nearest = zn.contacts[0]
        assert (nearest.key, nearest.residue, nearest.auth_seq_id) == ("A:3", "C", 3)
        assert nearest.min_distance == pytest.approx(2.2, abs=0.01)

    def test_contacts_are_sorted_nearest_first(self, complex_compounds: CompoundsResponse) -> None:
        for g in complex_compounds.groups:
            for instance in g.instances:
                distances = [c.min_distance for c in instance.contacts]
                assert distances == sorted(distances)

    def test_distant_groups_have_no_contacts(self, complex_compounds: CompoundsResponse) -> None:
        assert group(complex_compounds, "SO4").instances[0].contacts == []
        assert group(complex_compounds, "LIG").instances[0].contacts == []

    def test_dna_strand_is_described(self, complex_compounds: CompoundsResponse) -> None:
        (dna,) = complex_compounds.nucleic_acids
        assert (dna.label, dna.kind, dna.sequence, dna.length) == ("B", "DNA", "GCA", 3)
        assert dna.composition == {"A": 1, "C": 1, "G": 1}
        assert dna.gc_fraction == pytest.approx(2 / 3, abs=1e-4)
        assert "A:2" in {c.key for c in dna.contacts}  # placed 3.5 A from THR 2's CA

    def test_real_glycan_on_lysozyme(self) -> None:
        response = build(FIXTURES / "1HEW.pdb")
        nag = group(response, "NAG")
        assert nag.category == "carbohydrate"
        assert len(nag.instances) == 3
        assert nag.formula == "C8 H15 N O6"
        assert all(i.contacts for i in nag.instances)
        assert response.water_count == 103


# ------------------------------------------------------------ names and metadata


class TestComponentInfo:
    def test_hetnam_continuation_is_joined(self, complex_compounds: CompoundsResponse) -> None:
        assert group(complex_compounds, "HEM").name == (
            "PROTOPORPHYRIN IX CONTAINING FE (STAND-IN FOR A TEST, THREE ATOMS ONLY)"
        )

    def test_formul_copy_count_is_stripped(self) -> None:
        assert compounds._clean_formula("2(C8 H15 N O6)") == "C8 H15 N O6"
        assert compounds._clean_formula("C8 H15 N O6") == "C8 H15 N O6"
        assert compounds._clean_formula(None) is None

    def test_builtin_name_when_the_file_has_none(self, complex_compounds: CompoundsResponse) -> None:
        assert group(complex_compounds, "GLU").name == "Glutamic acid"
        assert group(complex_compounds, "LIG").name is None  # never invented

    def test_mmcif_chem_comp_loop_is_read(self, tmp_path: Path) -> None:
        cif = tmp_path / "x.cif"
        cif.write_text(
            "data_X\n"
            "loop_\n"
            "_chem_comp.id\n_chem_comp.type\n_chem_comp.name\n"
            "_chem_comp.formula\n_chem_comp.formula_weight\n"
            "ALA 'L-peptide linking' ALANINE 'C3 H7 N O2' 89.093\n"
            "NAG 'D-saccharide, beta linking' 2-acetamido-2-deoxy-beta-D-glucopyranose "
            "'C8 H15 N O6' 221.208\n"
            "ZN non-polymer 'ZINC ION' 'Zn 2' ?\n"
        )
        info = compounds.read_component_info(cif)
        assert info["ALA"].chem_type == "L-peptide linking"
        assert info["NAG"].name == "2-acetamido-2-deoxy-beta-D-glucopyranose"
        assert info["NAG"].formula_weight == pytest.approx(221.208)
        assert info["ZN"].name == "ZINC ION"
        assert info["ZN"].formula_weight is None  # '?' is "no value", not a number

    def test_mmcif_single_row_chem_comp_is_read(self, tmp_path: Path) -> None:
        cif = tmp_path / "y.cif"
        cif.write_text(
            "data_Y\n_chem_comp.id HEM\n_chem_comp.type non-polymer\n"
            "_chem_comp.name 'PROTOPORPHYRIN IX CONTAINING FE'\n"
        )
        assert compounds.read_component_info(cif)["HEM"].name == "PROTOPORPHYRIN IX CONTAINING FE"

    def test_unreadable_metadata_is_not_fatal(self, tmp_path: Path) -> None:
        assert compounds.read_component_info(tmp_path / "missing.pdb") == {}


class TestNotes:
    def test_bare_protein_says_so(self) -> None:
        response = build(FIXTURES / "1CRN.cif")
        assert response.groups == [] and response.nucleic_acids == []
        assert "no non-protein components" in response.notes[0]

    def test_complex_explains_additives_and_modified_residues(
        self, complex_compounds: CompoundsResponse
    ) -> None:
        text = " ".join(complex_compounds.notes)
        assert "Additives" in text
        assert "Modified residues" in text


# ------------------------------------------------------------ the API


def register(path: Path) -> str:
    uid, stored = storage.store_upload(path.read_bytes(), "pdb")
    registry.put(uid, parse(stored, uid))
    return uid


class TestEndpoint:
    def test_returns_compounds(self) -> None:
        uid = register(COMPLEX)
        response = client.get(f"/api/proteins/{uid}/compounds")
        assert response.status_code == 200
        body = response.json()
        assert body["protein_id"] == uid
        assert body["contact_cutoff"] == 4.0
        assert {g["code"] for g in body["groups"]} == {"SEP", "ZN", "GLU", "HEM", "SO4", "LIG"}
        assert body["nucleic_acids"][0]["label"] == "B"

    def test_unknown_protein_is_404(self) -> None:
        response = client.get("/api/proteins/00000000-0000-4000-8000-000000000000/compounds")
        assert response.status_code == 404

    def test_malformed_uid_is_404(self) -> None:
        assert client.get("/api/proteins/not-a-uid/compounds").status_code == 404

    def test_summary_lists_nucleic_acid_chains(self) -> None:
        response = client.post(
            "/api/proteins/upload",
            files={"file": ("complex.pdb", COMPLEX.read_bytes(), "chemical/x-pdb")},
        )
        assert response.status_code == 200
        assert response.json()["nucleic_acid_chains"] == ["B"]

    def test_nucleic_acid_only_upload_is_rejected_with_a_reason(self) -> None:
        response = client.post(
            "/api/proteins/upload",
            files={"file": ("dna.pdb", DNA_ONLY.encode(), "chemical/x-pdb")},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "nucleic-acid chains (B)" in detail
        assert "no protein chain" in detail
