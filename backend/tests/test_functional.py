"""A5 — the UniProt-to-structure mapping, ligand contacts, surface and priority.

The whole file is about one failure mode: a curated position placed on the
wrong residue. That failure is silent, it looks completely plausible in 3D, and
no user can check it, so the mapping gets more tests here than everything else
combined.

Two fixtures carry that weight:

* ``parity_multichain`` — the synthetic adversary. Chain H starts at author
  residue 27, has a numbering gap, an insertion code (34 then 34A), and a
  HETATM selenomethionine inside the polymer; chain M repeats chain H's
  sequence out of order; the HEM ligand is written under chain H's
  ``auth_asym_id`` while sitting against chain M. Anything that reads
  ``auth_seq_id`` as an ordinal, or attributes a ligand by chain label, fails
  here and only here.
* ``1HEW`` + ``uniprot_functional_P00698`` — the real one. UniProt P00698
  numbers hen lysozyme's 18-residue signal peptide; the crystal does not, so
  its curated active sites at 53 and 70 are Glu35 and Asp52 in the file, and
  its substrate-binding site at 119 is Asp101. Those three residues are
  textbook, so an off-by-anything mapping is falsifiable against the
  literature rather than against our own expectations.

Nothing here reaches the network: everything is either a pure function or a
committed file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.api.proteins import parse_structure_for_analytics
from app.models.protein import ChainInfo
from app.services import functional
from app.services.functional import ChainReadError, ChainResidues
from app.services.parser import parse
from tests.helpers import FIXTURES, load_json

PARITY_CIF = FIXTURES / "parity_multichain.cif"
PARITY_PDB = FIXTURES / "parity_multichain.pdb"
LYSOZYME = FIXTURES / "1HEW.pdb"
CRAMBIN = FIXTURES / "1CRN.cif"


def lysozyme_entry() -> dict:
    return load_json("uniprot_functional_P00698.json")


def egfr_entry() -> dict:
    return load_json("uniprot_functional_P00533.json")


def gagpol_entry() -> dict:
    return load_json("uniprot_functional_P04585.json")


def chains_of(path: Path) -> list[ChainResidues]:
    summary = parse(path, "u")
    return functional.read_chain_residues(parse_structure_for_analytics(path), summary)


def regions(path: Path, entry: dict | None, accession: str | None):
    summary = parse(path, "u")
    return functional.build_functional_regions(
        "u",
        summary,
        parse_structure_for_analytics(path),
        accession=accession,
        resolution_note="test",
        entry=entry,
    )


# ------------------------------------------------- reading the chain residues


@pytest.mark.parametrize("path", [PARITY_CIF, PARITY_PDB], ids=["mmcif", "pdb"])
def test_chain_sequences_match_the_parser(path: Path) -> None:
    """The re-walk must reproduce the parser's sequences exactly, both formats."""
    summary = parse(path, "u")
    chains = functional.read_chain_residues(parse_structure_for_analytics(path), summary)
    assert [(c.label, c.sequence) for c in chains] == [
        (c.label, c.sequence) for c in summary.chains
    ]


@pytest.mark.parametrize("path", [PARITY_CIF, PARITY_PDB], ids=["mmcif", "pdb"])
def test_ordinals_are_not_auth_seq_ids(path: Path) -> None:
    """Chain H's ordinals are 1-5 while the file numbers it 27, 28, 34, 34A, 35.

    The HETATM selenomethionine at 29 is skipped by the parser, so ordinal 3 is
    the glycine numbered 34 — not the residue numbered 29 and not the 3rd
    number in the file. And 34 appears twice: once plain, once with insertion
    code A. Any code that used the author number as an index would place a site
    on the wrong residue here without any symptom.
    """
    chain_h = next(c for c in chains_of(path) if c.label == "H")
    assert chain_h.sequence == "TAGSK"
    assert chain_h.auth_seq_ids == (27, 28, 34, 34, 35)
    assert chain_h.insertion_codes == (None, None, None, "A", None)
    assert [chain_h.ref(i).key for i in range(1, 6)] == [
        "H:1", "H:2", "H:3", "H:4", "H:5"
    ]
    assert chain_h.ref(4).auth_seq_id == 34
    assert chain_h.ref(4).insertion_code == "A"


@pytest.mark.parametrize("path", [PARITY_CIF, PARITY_PDB], ids=["mmcif", "pdb"])
def test_out_of_order_chain_keeps_file_order(path: Path) -> None:
    """Chain M lists the same residues as H but out of `label_seq_id` order.

    File order is what the parser and the Mol* index both use, so ordinal 1 of
    chain M is the glycine, not the threonine that sorts first.
    """
    chain_m = next(c for c in chains_of(path) if c.label == "M")
    assert chain_m.sequence == "GTASK"
    assert chain_m.auth_seq_ids == (34, 27, 28, 34, 35)


def test_read_chain_residues_refuses_a_summary_that_disagrees() -> None:
    """A parser/re-walk disagreement shifts every later ordinal. Refuse, loudly."""
    summary = parse(PARITY_CIF, "u")
    tampered = summary.model_copy(
        update={
            "chains": [
                ChainInfo(id="u:H", label="H", sequence="TAGS", residue_count=4),
                *summary.chains[1:],
            ]
        }
    )
    with pytest.raises(ChainReadError):
        functional.read_chain_residues(parse_structure_for_analytics(PARITY_CIF), tampered)


# ----------------------------------------------------- the position mapping


def test_mapping_offsets_by_the_alignment_not_by_position() -> None:
    """A five-residue N-terminal extension moves every position by five.

    The whole feature turns on this: UniProt position `p` is *not* ordinal `p`.
    """
    chain = ChainResidues(
        label="A",
        sequence="TAGSK",
        auth_seq_ids=(27, 28, 34, 34, 35),
        insertion_codes=(None, None, None, "A", None),
    )
    mapped = functional.map_uniprot_positions("MKWQVTAGSKLLNP", [chain])
    assert mapped.chains[0].mapped is True
    assert [ref.key for ref in mapped.positions[6]] == ["A:1"]
    assert [ref.key for ref in mapped.positions[10]] == ["A:5"]
    assert 5 not in mapped.positions
    assert 11 not in mapped.positions
    assert mapped.chains[0].uniprot_start == 6
    assert mapped.chains[0].uniprot_end == 10


def test_mapping_reports_the_offset_in_words() -> None:
    chain = ChainResidues("A", "TAGSK", (27, 28, 34, 34, 35), (None,) * 5)
    report = functional.map_uniprot_positions("MKWQVTAGSKLLNP", [chain]).chains[0]
    assert "UniProt 6-10" in report.offset_note
    assert "residues 1-5" in report.offset_note
    assert "27-35" in report.offset_note


def test_mapping_spans_an_internal_gap() -> None:
    """Unmodelled residues vanish from the chain sequence entirely.

    The parser concatenates across a gap, so a chain missing residues 4-8 of
    the entry is a contiguous string with no marker. Only an alignment can
    recover which side of the gap a position is on.
    """
    chain = ChainResidues("A", "MKWQNPTY", (1, 2, 3, 4, 5, 6, 7, 8), (None,) * 8)
    mapped = functional.map_uniprot_positions("MKWQCCCCCNPTY", [chain])
    assert [ref.ordinal for ref in mapped.positions[4]] == [4]
    assert [ref.ordinal for ref in mapped.positions[10]] == [5]
    assert 5 not in mapped.positions


def test_mapping_marks_every_copy_in_a_homo_oligomer() -> None:
    """One UniProt position, two identical chains, two marked residues."""
    chains = [
        ChainResidues("A", "TAGSK", (1, 2, 3, 4, 5), (None,) * 5),
        ChainResidues("B", "TAGSK", (1, 2, 3, 4, 5), (None,) * 5),
    ]
    mapped = functional.map_uniprot_positions("TAGSK", chains)
    assert sorted(ref.key for ref in mapped.positions[3]) == ["A:3", "B:3"]


def test_mapping_refuses_a_chain_that_is_a_different_molecule() -> None:
    """A binding partner in the same file must not inherit the entry's sites.

    Chain B here aligns end to end — the aligner will always find *an*
    alignment — but at 25% identity. Only the identity floor separates it from
    chain A, which is why the floor is the thing under test.
    """
    reference = "TAGSKLMNPQRSTVWY"
    chains = [
        ChainResidues("A", reference, tuple(range(1, 17)), (None,) * 16),
        ChainResidues("B", "TAGSAAAAAAAAAAAA", tuple(range(1, 17)), (None,) * 16),
    ]
    mapped = functional.map_uniprot_positions(reference, chains)
    by_chain = {report.chain: report for report in mapped.chains}
    assert by_chain["A"].mapped is True
    assert by_chain["B"].mapped is False
    assert by_chain["B"].aligned_columns == 16
    assert by_chain["B"].identity_percent == 25.0
    assert "not close enough to be the same molecule" in by_chain["B"].note
    assert all(ref.chain == "A" for refs in mapped.positions.values() for ref in refs)


def test_mapping_refuses_a_chain_the_aligner_cannot_overlap_at_all() -> None:
    """A poly-tryptophan chain scores so badly the aligner overlaps nothing."""
    report = functional.map_uniprot_positions(
        "TAGSKLMNPQ", [ChainResidues("B", "W" * 10, tuple(range(1, 11)), (None,) * 10)]
    ).chains[0]
    assert report.mapped is False
    assert report.aligned_columns == 0
    assert "too few to place a position on" in report.note


def test_mapping_refuses_a_chain_too_short_to_be_unambiguous() -> None:
    chain = ChainResidues("A", "TAG", (1, 2, 3), (None, None, None))
    report = functional.map_uniprot_positions("MKWQVTAGSKLLNP", [chain]).chains[0]
    assert report.mapped is False
    assert "fewer than 4" in report.note


def test_mapping_refuses_when_uniprot_has_no_sequence() -> None:
    chain = ChainResidues("A", "TAGSK", (1, 2, 3, 4, 5), (None,) * 5)
    report = functional.map_uniprot_positions("", [chain]).chains[0]
    assert report.mapped is False
    assert "no usable sequence" in report.note


def test_mapping_refuses_an_alignment_past_the_interactive_limit() -> None:
    """The bound is on len(a) * len(b), which is the work, not on either length."""
    long_chain = ChainResidues(
        "A", "A" * 5000, tuple(range(1, 5001)), (None,) * 5000
    )
    report = functional.map_uniprot_positions("A" * 5000, [long_chain]).chains[0]
    assert report.mapped is False
    assert "interactive limit" in report.note


def test_mapping_ignores_unknown_residues_in_the_identity() -> None:
    """'X' is the parser's placeholder; it is neither a match nor a mismatch.

    Counting X as a mismatch would push a lightly-modified chain under the
    identity floor and refuse a mapping that is perfectly sound.
    """
    chain = ChainResidues("A", "TAXSKLMNPQ", tuple(range(1, 11)), (None,) * 10)
    report = functional.map_uniprot_positions("TAGSKLMNPQ", [chain]).chains[0]
    assert report.mapped is True
    assert report.identity_percent == 100.0


def test_mapping_refuses_a_chain_that_is_all_unknown_residues() -> None:
    chain = ChainResidues("A", "XXXXXXXXXX", tuple(range(1, 11)), (None,) * 10)
    report = functional.map_uniprot_positions("TAGSKLMNPQ", [chain]).chains[0]
    assert report.mapped is False
    assert "too few to place a position on" in report.note


# -------------------------------------------- the real lysozyme mapping case


def test_lysozyme_active_sites_land_on_glu35_and_asp52() -> None:
    """UniProt 53 and 70 are Glu35 and Asp52 of every lysozyme structure.

    This is the assertion the whole module exists for. The offset is the
    18-residue signal peptide UniProt numbers and no crystal contains.
    """
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    placed = {
        site.uniprot_start: [(ref.key, ref.residue, ref.auth_seq_id) for ref in site.positions]
        for site in payload.active_sites
    }
    assert placed == {
        53: [("A:35", "E", 35)],
        70: [("A:52", "D", 52)],
    }
    assert all(site.located for site in payload.active_sites)


def test_lysozyme_binding_site_lands_on_asp101() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (site,) = payload.binding_sites
    assert site.uniprot_start == 119
    assert site.ligand == "substrate"
    assert [(ref.key, ref.residue) for ref in site.positions] == [("A:101", "D")]


def test_lysozyme_chain_mapping_states_the_signal_peptide_offset() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (report,) = payload.chain_mappings
    assert report.mapped is True
    assert report.identity_percent == 100.0
    assert report.uniprot_start == 19
    assert report.uniprot_end == 147
    assert "UniProt 19-147 covers chain A residues 1-129" in report.offset_note


def test_lysozyme_curated_residue_letters_match_uniprot() -> None:
    """Cross-check: the residue found in the file is the residue UniProt names."""
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    for site in payload.active_sites + payload.binding_sites:
        assert site.uniprot_residues == "".join(ref.residue for ref in site.positions)
        assert site.substitutions == []


# --------------------------------------------------------- observed ligands


@pytest.mark.parametrize("path", [PARITY_CIF, PARITY_PDB], ids=["mmcif", "pdb"])
def test_ligand_contacts_are_geometric_not_by_chain_label(path: Path) -> None:
    """HEM is written under chain H but touches chain M's lysine, and only it."""
    payload = regions(path, None, None)
    (ligand,) = payload.ligands
    assert ligand.component == "HEM"
    assert ligand.chain == "H"
    assert ligand.single_atom is True
    assert [(c.key, c.residue) for c in ligand.contacts] == [("M:5", "K")]
    assert ligand.contacts[0].min_distance == pytest.approx(1.73, abs=0.01)


@pytest.mark.parametrize("path", [PARITY_CIF, PARITY_PDB], ids=["mmcif", "pdb"])
def test_waters_and_in_chain_modified_residues_are_not_ligands(path: Path) -> None:
    """Two HOH and one HETATM selenomethionine are all in this file. None is a ligand."""
    payload = regions(path, None, None)
    assert [ligand.component for ligand in payload.ligands] == ["HEM"]


def test_lysozyme_ligand_contacts_include_the_curated_binding_residue() -> None:
    """Asp101 is both curated by UniProt and observed touching the tri-NAG."""
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    assert [ligand.component for ligand in payload.ligands] == ["NAG", "NAG", "NAG"]
    touched = {c.key for ligand in payload.ligands for c in ligand.contacts}
    # Subsites A-C of the cleft, the residues every lysozyme paper names.
    assert {"A:59", "A:62", "A:63", "A:101", "A:107", "A:108"} <= touched
    assert payload.contact_cutoff == functional.CONTACT_CUTOFF_ANGSTROMS


def test_ligand_contacts_are_sorted_closest_first() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    for ligand in payload.ligands:
        distances = [contact.min_distance for contact in ligand.contacts]
        assert distances == sorted(distances)
        assert all(d <= functional.CONTACT_CUTOFF_ANGSTROMS for d in distances)


def test_an_apo_structure_says_so_rather_than_predicting_a_pocket() -> None:
    payload = regions(CRAMBIN, None, None)
    assert payload.ligands == []
    assert any("No non-water ligand" in note for note in payload.notes)
    assert any("does not predict pockets" in note for note in payload.notes)


# --------------------------------------------- surface hydrophobicity + charge


def test_surface_profile_arrays_are_indexed_by_ordinal() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (profile,) = payload.surface
    assert profile.chain == "A"
    assert len(profile.sequence) == 129
    assert len(profile.hydropathy) == 129
    assert len(profile.charge) == 129
    assert len(profile.relative_accessibility) == 129
    assert len(profile.surface_exposed) == 129
    # Ordinal 35 is Glu35: negative, and buried in the cleft.
    assert profile.sequence[34] == "E"
    assert profile.charge[34] == -1
    assert profile.relative_accessibility[34] < functional.EXPOSURE_THRESHOLD


def test_surface_charge_uses_formal_charge_and_counts_histidine_apart() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (profile,) = payload.surface
    sequence = profile.sequence
    expected = sequence.count("K") + sequence.count("R") - sequence.count("D") - sequence.count("E")
    assert profile.net_charge == expected
    assert profile.histidine_count == sequence.count("H")
    assert all(profile.charge[i] == 0 for i, aa in enumerate(sequence) if aa == "H")


def test_surface_hydropathy_matches_the_shared_kyte_doolittle_scale() -> None:
    """One scale, shared with `analytics.hydrophobicity_profile`. No second copy."""
    from app.services.analytics import KD_HYDROPATHY

    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (profile,) = payload.surface
    assert profile.hydropathy == [KD_HYDROPATHY[aa] for aa in profile.sequence]


def test_surface_means_are_computed_over_exposed_residues_only() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (profile,) = payload.surface
    exposed = [
        value for value, flag in zip(profile.hydropathy, profile.surface_exposed) if flag
    ]
    assert profile.surface_mean_hydropathy == pytest.approx(
        round(sum(exposed) / len(exposed), 4)
    )
    assert profile.surface_mean_hydropathy != profile.mean_hydropathy


def test_accessibility_is_computed_without_waters_or_ligand() -> None:
    """Leaving solvent in would bury exactly the pocket residues being reported."""
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    assert "waters and ligands removed" in payload.surface_note
    assert functional.strip_non_polymer(parse_structure_for_analytics(LYSOZYME)) == 106


def test_accessibility_is_skipped_rather_than_guessed_when_too_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past the atom bound the arrays are empty and the note says why.

    Hydropathy and charge are unaffected — the limit never truncates them.
    """
    monkeypatch.setattr(functional, "MAX_SASA_ATOMS", 10)
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (profile,) = payload.surface
    assert profile.relative_accessibility == []
    assert profile.surface_exposed == []
    assert profile.surface_mean_hydropathy is None
    assert len(profile.hydropathy) == 129
    assert "past the 10-atom limit" in payload.surface_note


# --------------------------------------------------------- priority residues


def test_priority_ranks_converging_evidence_first() -> None:
    """Asp101 is curated AND observed touching the ligand, so it leads."""
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    top = payload.priority_residues[0]
    assert top.key == "A:101"
    assert top.evidence_kinds == 2
    assert sorted(top.provenance) == ["structure", "uniprot"]
    assert top.curated_binding_site is True
    assert top.ligand_contact is True
    assert all(
        payload.priority_residues[i].evidence_kinds
        >= payload.priority_residues[i + 1].evidence_kinds
        for i in range(len(payload.priority_residues) - 1)
    )


def test_priority_residues_carry_their_own_chemistry() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    (profile,) = payload.surface
    for residue in payload.priority_residues:
        index = residue.ordinal - 1
        assert residue.hydropathy == profile.hydropathy[index]
        assert residue.charge == profile.charge[index]
        assert residue.relative_accessibility == profile.relative_accessibility[index]


def test_priority_residues_use_the_selection_key_format() -> None:
    payload = regions(LYSOZYME, lysozyme_entry(), "P00698")
    for residue in payload.priority_residues:
        assert residue.key == f"{residue.chain}:{residue.ordinal}"


def test_regions_are_not_priority_residues() -> None:
    """A 48-residue DNA-binding domain would bury the handful that matter."""
    entry = gagpol_entry()
    chain = ChainResidues(
        "A",
        functional.entry_sequence(entry)[1369:1417],
        tuple(range(1, 49)),
        (None,) * 48,
    )
    mapped = functional.map_uniprot_positions(functional.entry_sequence(entry), [chain])
    buckets = functional.curated_sites(entry, mapped, "P04585")
    (dna,) = buckets["dna_binding"]
    assert dna.located is True
    assert len(dna.positions) == 48
    priority = functional.priority_residues([], [], [], [])
    assert priority == []


# --------------------------------------------- refusing rather than guessing


def test_a_site_outside_the_construct_is_reported_unplaced() -> None:
    """EGFR's kinase sites do not exist in a lysozyme file. Say so, place nothing."""
    payload = regions(LYSOZYME, egfr_entry(), "P00533")
    (report,) = payload.chain_mappings
    assert report.mapped is False
    assert payload.active_sites and all(not s.located for s in payload.active_sites)
    assert all(site.positions == [] for site in payload.active_sites)
    assert "No chain in this structure could be aligned" in (
        payload.active_sites[0].location_note
    )
    assert payload.unlocated_sites == len(
        payload.active_sites + payload.binding_sites + payload.other_sites
    )
    assert any("could not be placed in this structure" in n for n in payload.notes)


def test_a_site_the_construct_does_not_reach_is_reported_unplaced() -> None:
    """The chain maps, but the curated position is off the end of it.

    A 22-residue N-terminal fragment of lysozyme contains none of the three
    curated sites, so all three come back with `located` false and a note —
    not with a position on whatever residue happened to be nearest.
    """
    entry = lysozyme_entry()
    reference = functional.entry_sequence(entry)
    chain = ChainResidues("A", reference[18:40], tuple(range(1, 23)), (None,) * 22)
    mapped = functional.map_uniprot_positions(reference, [chain])
    assert mapped.chains[0].mapped is True

    buckets = functional.curated_sites(entry, mapped, "P00698")
    sites = buckets["active_site"] + buckets["binding_site"]
    assert len(sites) == 3
    for site in sites:
        assert site.located is False
        assert site.positions == []
        assert "could not be located in this structure" in site.location_note


def test_partially_present_feature_reports_which_positions_are_missing() -> None:
    """A truncated construct keeps the half it has and names the half it lacks."""
    entry = egfr_entry()
    reference = functional.entry_sequence(entry)
    # A construct covering UniProt 720-760: the ATP P-loop at 718-726 is only
    # half present, so four of its nine positions have nowhere to go.
    chain = ChainResidues(
        "A", reference[719:760], tuple(range(720, 761)), (None,) * 41
    )
    mapped = functional.map_uniprot_positions(reference, [chain])
    buckets = functional.curated_sites(entry, mapped, "P00533")
    ploop = next(s for s in buckets["binding_site"] if s.uniprot_start == 718)
    assert ploop.located is True
    assert [ref.ordinal for ref in ploop.positions] == [1, 2, 3, 4, 5, 6, 7]
    assert "718-719" in ploop.location_note


def test_a_substitution_is_reported_not_hidden_and_does_not_move_the_marker() -> None:
    """An engineered mutant still maps; the difference is stated on the site."""
    entry = lysozyme_entry()
    reference = functional.entry_sequence(entry)
    mutated = reference[18:52] + "A" + reference[53:]
    chain = ChainResidues("A", mutated, tuple(range(1, len(mutated) + 1)), (None,) * len(mutated))
    mapped = functional.map_uniprot_positions(reference, [chain])
    buckets = functional.curated_sites(entry, mapped, "P00698")
    glu35 = next(s for s in buckets["active_site"] if s.uniprot_start == 53)
    assert [ref.key for ref in glu35.positions] == ["A:35"]
    assert glu35.substitutions == ["A:35 is A here but E in UniProt"]


def test_an_isoform_scoped_feature_is_never_placed_on_the_canonical_numbering() -> None:
    entry = lysozyme_entry()
    features = [dict(f) for f in entry["features"]]
    features[0] = {
        **features[0],
        "location": {**features[0]["location"], "sequence": "P00698-2"},
    }
    entry = {**entry, "features": features}
    payload = functional.build_functional_regions(
        "u",
        parse(LYSOZYME, "u"),
        parse_structure_for_analytics(LYSOZYME),
        accession="P00698",
        resolution_note="test",
        entry=entry,
    )
    isoform_site = next(s for s in payload.active_sites if s.uniprot_start == 53)
    assert isoform_site.located is False
    assert isoform_site.positions == []
    assert "isoform P00698-2" in isoform_site.location_note


def test_a_feature_with_no_resolvable_location_is_dropped() -> None:
    entry = lysozyme_entry()
    features = [
        {
            "type": "Active site",
            "location": {
                "start": {"value": None, "modifier": "UNKNOWN"},
                "end": {"value": None, "modifier": "UNKNOWN"},
            },
        },
        *entry["features"],
    ]
    chain = ChainResidues("A", functional.entry_sequence(entry)[18:], tuple(range(1, 130)), (None,) * 129)
    mapped = functional.map_uniprot_positions(functional.entry_sequence(entry), [chain])
    buckets = functional.curated_sites({**entry, "features": features}, mapped, "P00698")
    assert len(buckets["active_site"]) == 2


def test_no_accession_still_returns_the_observed_half() -> None:
    """A plain upload with a ligand is not empty just because UniProt knows nothing."""
    payload = regions(LYSOZYME, None, None)
    assert payload.accession_resolved is False
    assert payload.active_sites == []
    assert payload.chain_mappings == []
    assert len(payload.ligands) == 3
    assert payload.surface and payload.priority_residues


def test_a_chain_read_failure_publishes_nothing_positional() -> None:
    summary = parse(LYSOZYME, "u")
    broken = summary.model_copy(
        update={"chains": [ChainInfo(id="u:A", label="A", sequence="KVF", residue_count=3)]}
    )
    payload = functional.build_functional_regions(
        "u",
        broken,
        parse_structure_for_analytics(LYSOZYME),
        accession="P00698",
        resolution_note="test",
        entry=lysozyme_entry(),
    )
    assert payload.ligands == []
    assert payload.surface == []
    assert payload.priority_residues == []
    assert any("could not be verified" in note for note in payload.notes)


# --------------------------------------------------- the recorded field shape


def test_recorded_entries_carry_the_feature_types_we_ask_for() -> None:
    """Guards the field names against a UniProt schema change going unnoticed.

    `ft_metal` / `ft_np_bind` / `ft_ca_bind` no longer exist upstream; metal and
    nucleotide binding arrive folded into `ft_binding` with a `ligand` object,
    which is what the Mg(2+) sites below are.
    """
    types = {feature["type"] for feature in gagpol_entry()["features"]}
    assert {"Active site", "Binding site", "Site", "DNA binding"} <= types
    magnesium = [
        f for f in gagpol_entry()["features"] if (f.get("ligand") or {}).get("name") == "Mg(2+)"
    ]
    assert magnesium, "ft_binding is expected to carry the old ft_metal content"


def test_evidence_is_split_into_experimental_and_inferred() -> None:
    """A PROSITE rule and a PDB observation must not read the same in the UI."""
    entry = egfr_entry()
    reference = functional.entry_sequence(entry)
    chain = ChainResidues("A", reference, tuple(range(1, len(reference) + 1)), (None,) * len(reference))
    mapped = functional.map_uniprot_positions(reference, [chain])
    buckets = functional.curated_sites(entry, mapped, "P00533")
    (active,) = buckets["active_site"]
    assert active.evidence_codes == ["ECO:0000255"]
    assert active.experimental is False
    atp = next(s for s in buckets["binding_site"] if s.uniprot_start == 718)
    assert atp.experimental is True
    assert atp.ligand == "ATP"
    assert atp.label == "Binding site (ATP)"


def test_an_alphafold_model_maps_one_to_one() -> None:
    """The no-offset case: an AlphaFold model covers the whole UniProt sequence."""
    entry = egfr_entry()
    reference = functional.entry_sequence(entry)
    chain = ChainResidues("A", reference, tuple(range(1, len(reference) + 1)), (None,) * len(reference))
    mapped = functional.map_uniprot_positions(reference, [chain])
    assert mapped.chains[0].uniprot_start == 1
    assert mapped.chains[0].uniprot_end == len(reference)
    assert [ref.ordinal for ref in mapped.positions[837]] == [837]
