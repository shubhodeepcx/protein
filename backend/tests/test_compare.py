"""Unit + endpoint tests for the P7 comparison view (spec A3).

Nothing here reaches the network: every input is either a committed fixture or
built in-process. The comparison endpoint has no external leg at all, so unlike
`search` and `annotations` there is nothing to mock.

The load-bearing tests in this file are the superposition ones. The
least-squares fit itself is BioPython's `Superimposer` and is trusted; what is
tested is the *residue pairing* that feeds it, because a pairing that silently
slips by one produces a confident and completely wrong RMSD. Every superposition
fixture is a rigid transform of one reference, so the correct answer is exactly
0.0 and any mispairing shows up as a large number rather than as a judgement
call.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from Bio.PDB import MMCIFParser, PDBParser
from fastapi.testclient import TestClient

from app.main import app
from app.models.compare import SequenceAlignment
from app.models.protein import ChainInfo
from app.services import compare, parser

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STATIC = Path(__file__).resolve().parents[1] / "app" / "static"

client = TestClient(app)


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #


def _summary(name: str, uid: str):
    """Parse a fixture through the real parser, as an upload would be."""
    return parser.parse(_path(name), uid)


def _path(name: str) -> Path:
    return STATIC / name if (STATIC / name).exists() else FIXTURES / name


def _structure(name: str):
    path = _path(name)
    bio = MMCIFParser(QUIET=True) if path.suffix.lower() in (".cif", ".mmcif") else PDBParser(QUIET=True)
    return bio.get_structure(path.stem, str(path))


def _chain(name: str, uid: str, label: str | None = None) -> ChainInfo:
    summary = _summary(name, uid)
    picked = compare.primary_chain(summary, label)
    assert picked is not None
    return picked


def _synthetic_alignment(row_a: str, row_b: str, **overrides) -> SequenceAlignment:
    """A `SequenceAlignment` with the given rows and otherwise plausible fields.

    Used only where a test needs to drive `superpose` with an alignment it could
    not easily provoke from real sequences (a twilight-zone identity on an
    8-residue fixture, for instance). `align_chains` is tested separately.
    """
    fields: dict[str, object] = {
        "chain_a": "A",
        "chain_b": "A",
        "length_a": len(row_a.replace(compare.GAP, "")),
        "length_b": len(row_b.replace(compare.GAP, "")),
        "alignment_length": len(row_a),
        "aligned_columns": len(row_a),
        "identities": len(row_a),
        "similarities": len(row_a),
        "gap_columns": 0,
        "identity_percent": 100.0,
        "similarity_percent": 100.0,
        "identity_percent_aligned": 100.0,
        "score": 0.0,
        "aligned_a": row_a,
        "aligned_b": row_b,
        "match_line": "|" * len(row_a),
    }
    fields.update(overrides)
    return SequenceAlignment(**fields)


def _upload(filename: str) -> str:
    """Upload a fixture through the real endpoint and return its uid."""
    payload = _path(filename).read_bytes()
    media = "chemical/x-pdb" if filename.endswith(".pdb") else "chemical/x-mmcif"
    res = client.post("/api/proteins/upload", files={"file": (filename, payload, media)})
    assert res.status_code == 200, res.text
    return res.json()["id"]


# --------------------------------------------------------------------------- #
# the parser seam: sequence index -> residue object                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fixture", ["parity_multichain.pdb", "parity_multichain.cif"])
def test_polymer_residues_lines_up_with_the_parsers_sequence(fixture: str) -> None:
    """`polymer_residues[i]` must be the residue that produced `sequence[i]`.

    This is the assumption every paired CA atom rests on. `parity_multichain`
    is the adversarial case on purpose: it has HETATM residues the parser skips,
    an insertion code, a numbering gap, chains that do not start at 1, and a
    ligand-only chain. Comparing against `parser.parse` — rather than against a
    hand-written expectation — means this fails if either side drifts.

    It deliberately does NOT touch `parser.py` or `residue-index.ts`; it only
    pins that `compare.py` reads the same residues the parser did.
    """
    summary = _summary(fixture, "seam")
    structure = _structure(fixture)

    assert summary.chains, "fixture should parse into at least one chain"
    for chain in summary.chains:
        residues = compare.polymer_residues(structure, chain.label)
        assert len(residues) == len(chain.sequence), (
            f"chain {chain.label}: {len(residues)} residues vs "
            f"{len(chain.sequence)} sequence characters"
        )
        rebuilt = "".join(
            parser._AA_THREE_TO_ONE.get(r.get_resname().upper(), "X") for r in residues
        )
        assert rebuilt == chain.sequence


def test_polymer_residues_is_empty_for_an_unknown_chain() -> None:
    assert compare.polymer_residues(_structure("superpose_ref.pdb"), "Z") == []


# --------------------------------------------------------------------------- #
# primary_chain                                                                #
# --------------------------------------------------------------------------- #


def test_primary_chain_picks_the_longest() -> None:
    summary = _summary("parity_multichain.pdb", "primary")
    picked = compare.primary_chain(summary)
    assert picked is not None
    assert picked.residue_count == max(c.residue_count for c in summary.chains)


def test_primary_chain_breaks_ties_on_label() -> None:
    """Equal-length chains must resolve the same way on every request."""
    summary = _summary("superpose_ref.pdb", "tie")
    chains = [
        ChainInfo(id="x:B", label="B", sequence="ACDE", residue_count=4),
        ChainInfo(id="x:A", label="A", sequence="ACDE", residue_count=4),
    ]
    summary.chains = chains
    assert compare.primary_chain(summary) is not None
    assert compare.primary_chain(summary).label == "A"


def test_primary_chain_honours_an_explicit_label() -> None:
    summary = _summary("parity_multichain.pdb", "explicit")
    labels = [c.label for c in summary.chains]
    picked = compare.primary_chain(summary, labels[-1])
    assert picked is not None and picked.label == labels[-1]


def test_primary_chain_returns_none_for_an_unknown_label() -> None:
    summary = _summary("superpose_ref.pdb", "unknown")
    assert compare.primary_chain(summary, "Z") is None


def test_primary_chain_returns_none_when_there_are_no_chains() -> None:
    summary = _summary("superpose_ref.pdb", "empty")
    summary.chains = []
    assert compare.primary_chain(summary) is None


# --------------------------------------------------------------------------- #
# align_chains                                                                 #
# --------------------------------------------------------------------------- #


def test_alignment_of_identical_chains_is_fully_identical() -> None:
    chain = _chain("superpose_ref.pdb", "a")
    result = compare.align_chains(chain, chain)
    assert result.identity_percent == 100.0
    assert result.similarity_percent == 100.0
    assert result.alignment_length == result.aligned_columns == 8
    assert result.gap_columns == 0
    assert result.match_line == "|" * 8


def test_alignment_places_a_gap_where_residues_were_deleted() -> None:
    """The exact alignment is pinned: the RMSD pairing is derived from it."""
    result = compare.align_chains(
        _chain("superpose_ref.pdb", "a"), _chain("superpose_gapped.pdb", "b")
    )
    assert result.aligned_a == "ACDEFGHI"
    assert result.aligned_b == "ACD--GHI"
    assert result.match_line == "|||  |||"
    assert result.identities == 6
    assert result.gap_columns == 2
    assert result.aligned_columns == 6
    # Two denominators, two answers: 6/8 over the whole alignment, 6/6 over the
    # region that actually overlaps.
    assert result.identity_percent == 75.0
    assert result.identity_percent_aligned == 100.0


def test_unknown_residues_never_count_as_identical() -> None:
    """'X' is the parser's placeholder for a non-standard residue.

    Two placeholders are two unknowns. Counting X against X as a match would
    inflate identity for exactly the structures — heavily modified ones — where
    it is least justified.
    """
    left = ChainInfo(id="l:A", label="A", sequence="ACXDE", residue_count=5)
    right = ChainInfo(id="r:A", label="A", sequence="ACXDE", residue_count=5)
    result = compare.align_chains(left, right)
    assert result.aligned_columns == 5
    assert result.identities == 4
    assert result.similarities == 4
    # The X column is blank in the match line, between four identities.
    assert result.match_line == "|| ||"


def test_similarity_counts_conservative_substitutions_identity_does_not() -> None:
    """A '+' column: different residue, positive BLOSUM62 score."""
    # K/R (lysine/arginine) score +2 in BLOSUM62 — the textbook conservative
    # substitution. D/W scores -4 and must count as neither.
    left = ChainInfo(id="l:A", label="A", sequence="AAKAAD", residue_count=6)
    right = ChainInfo(id="r:A", label="A", sequence="AARAAW", residue_count=6)
    result = compare.align_chains(left, right)
    assert result.aligned_columns == 6
    assert result.identities == 4
    assert result.similarities == 5
    assert result.match_line == "||+|| "
    assert result.similarity_percent > result.identity_percent


def test_end_gaps_are_free_so_a_fragment_aligns_into_the_full_sequence() -> None:
    """A3's headline case: a short construct against a full-length model.

    With end gaps charged, the aligner is pushed into breaking up the matching
    core to shorten the overhang. With them free, the fragment lands in one
    piece — and the two identity denominators then say different, both-true
    things about the same alignment.
    """
    full = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIE"
    fragment = full[10:22]
    left = ChainInfo(id="l:A", label="A", sequence=full, residue_count=len(full))
    right = ChainInfo(id="r:A", label="A", sequence=fragment, residue_count=len(fragment))
    result = compare.align_chains(left, right)

    assert result.aligned_a == full
    assert result.aligned_b == "-" * 10 + fragment + "-" * (len(full) - 22)
    # The fragment is contiguous: no internal gap was opened inside it.
    assert result.aligned_b.strip("-") == fragment
    assert result.aligned_columns == len(fragment)
    assert result.identity_percent_aligned == 100.0
    assert result.identity_percent == pytest.approx(100.0 * len(fragment) / len(full), abs=0.01)


def test_alignment_refuses_chains_over_the_size_limit() -> None:
    oversized = "A" * (compare.MAX_ALIGNABLE_RESIDUES + 1)
    left = ChainInfo(id="l:A", label="A", sequence=oversized, residue_count=len(oversized))
    right = ChainInfo(id="r:A", label="A", sequence="ACDE", residue_count=4)
    with pytest.raises(compare.AlignmentTooLargeError):
        compare.align_chains(left, right)


# --------------------------------------------------------------------------- #
# paired_indices                                                               #
# --------------------------------------------------------------------------- #


def test_paired_indices_skips_gap_columns_on_both_sides() -> None:
    """Each side's index advances only on its own non-gap characters."""
    assert compare.paired_indices("ACDEFGHI", "ACD--GHI") == [
        (0, 0), (1, 1), (2, 2), (5, 3), (6, 4), (7, 5),
    ]


def test_paired_indices_handles_gaps_on_the_other_side_too() -> None:
    assert compare.paired_indices("AB--EF", "ABCDEF") == [(0, 0), (1, 1), (2, 4), (3, 5)]


def test_paired_indices_is_empty_when_nothing_overlaps() -> None:
    assert compare.paired_indices("AB--", "--CD") == []


# --------------------------------------------------------------------------- #
# superpose                                                                    #
# --------------------------------------------------------------------------- #


def test_rigid_transform_superposes_to_zero_rmsd() -> None:
    """`superpose_rigid.pdb` is the reference rotated 30 deg and translated.

    Recovering RMSD 0 means the fit actually solved for that transform.
    """
    chain_a = _chain("superpose_ref.pdb", "a")
    chain_b = _chain("superpose_rigid.pdb", "b")
    alignment = compare.align_chains(chain_a, chain_b)
    outcome = compare.superpose(
        _structure("superpose_ref.pdb"), _structure("superpose_rigid.pdb"),
        alignment, chain_a, chain_b,
    )
    assert outcome.result is not None
    assert outcome.result.rmsd == pytest.approx(0.0, abs=1e-3)
    assert outcome.result.atom_pairs == 8
    assert outcome.result.residue_pairs == 8


def test_gapped_alignment_pairs_residues_through_the_gap() -> None:
    """The test that discriminates a correct pairing from a plausible one.

    `superpose_gapped.pdb` is the transformed reference with residues 4 and 5
    deleted, so the alignment carries a two-column gap. A gap-aware pairing maps
    reference residues 6,7,8 onto the gapped file's 4,5,6 and recovers RMSD 0.
    An index-to-index pairing maps 6,7,8 onto 6,7,8 — three residues that do not
    exist in the same places — and cannot.
    """
    chain_a = _chain("superpose_ref.pdb", "a")
    chain_b = _chain("superpose_gapped.pdb", "b")
    alignment = compare.align_chains(chain_a, chain_b)
    outcome = compare.superpose(
        _structure("superpose_ref.pdb"), _structure("superpose_gapped.pdb"),
        alignment, chain_a, chain_b,
    )
    assert outcome.result is not None
    assert outcome.result.rmsd == pytest.approx(0.0, abs=1e-3)
    assert outcome.result.atom_pairs == 6
    assert outcome.result.residue_pairs == 6


def test_a_residue_without_an_alpha_carbon_is_dropped_from_the_fit() -> None:
    """It stays a residue pair — it just is not an atom pair."""
    chain_a = _chain("superpose_ref.pdb", "a")
    chain_b = _chain("superpose_noca.pdb", "b")
    alignment = compare.align_chains(chain_a, chain_b)
    outcome = compare.superpose(
        _structure("superpose_ref.pdb"), _structure("superpose_noca.pdb"),
        alignment, chain_a, chain_b,
    )
    assert outcome.result is not None
    assert outcome.result.residue_pairs == 6
    assert outcome.result.atom_pairs == 5
    assert outcome.result.rmsd == pytest.approx(0.0, abs=1e-3)


def test_superposition_is_refused_below_three_atom_pairs() -> None:
    """Two points leave a whole axis of rotation free. No RMSD is honest here."""
    chain_a = _chain("superpose_ref.pdb", "a")
    chain_b = _chain("superpose_short.pdb", "b")
    alignment = compare.align_chains(chain_a, chain_b)
    outcome = compare.superpose(
        _structure("superpose_ref.pdb"), _structure("superpose_short.pdb"),
        alignment, chain_a, chain_b,
    )
    assert outcome.result is None
    assert "below the 3 needed" in outcome.note


def test_superposition_is_refused_when_residues_and_sequence_disagree() -> None:
    """The guard against pairing through a sequence the file does not support.

    If this module and the parser ever disagree about which residues are
    polymer, every pair after the divergence is wrong. Refusing is the only safe
    answer; a shorter fit over the prefix would look fine and be wrong.
    """
    chain_a = _chain("superpose_ref.pdb", "a")
    truncated = ChainInfo(
        id="b:A", label="A", sequence="ACDEFGH", residue_count=7  # file has 8
    )
    alignment = _synthetic_alignment("ACDEFGHI", "ACDEFGH-")
    outcome = compare.superpose(
        _structure("superpose_ref.pdb"), _structure("superpose_ref.pdb"),
        alignment, chain_a, truncated,
    )
    assert outcome.result is None
    assert "do not line up" in outcome.note


def test_low_identity_is_flagged_rather_than_refused() -> None:
    """A3 wants similar folds at low identity, so the number is still returned."""
    chain_a = _chain("superpose_ref.pdb", "a")
    chain_b = _chain("superpose_rigid.pdb", "b")
    alignment = _synthetic_alignment(
        "ACDEFGHI", "ACDEFGHI", identity_percent_aligned=9.0, identity_percent=9.0
    )
    outcome = compare.superpose(
        _structure("superpose_ref.pdb"), _structure("superpose_rigid.pdb"),
        alignment, chain_a, chain_b,
    )
    assert outcome.result is not None
    assert outcome.result.rmsd == pytest.approx(0.0, abs=1e-3)
    assert outcome.result.caveat is not None
    assert "twilight zone" in outcome.result.caveat


def test_a_well_supported_fit_carries_no_caveat() -> None:
    """1CRN against itself in the other file format: 46 pairs, full identity."""
    chain_a = _chain("1CRN.pdb", "a")
    chain_b = _chain("1CRN.cif", "b")
    alignment = compare.align_chains(chain_a, chain_b)
    outcome = compare.superpose(
        _structure("1CRN.pdb"), _structure("1CRN.cif"), alignment, chain_a, chain_b
    )
    assert outcome.result is not None
    assert outcome.result.rmsd == pytest.approx(0.0, abs=1e-3)
    assert outcome.result.atom_pairs == 46
    assert outcome.result.caveat is None


# --------------------------------------------------------------------------- #
# the diff tables                                                              #
# --------------------------------------------------------------------------- #


def _analytics(uid: str):
    from app.api.proteins import compute_analytics

    summary = registry_summary(uid)
    return compute_analytics(uid, summary, Path(_stored_path(uid)))


def registry_summary(uid: str):
    from app.services import registry

    summary = registry.get(uid)
    assert summary is not None
    return summary


def _stored_path(uid: str) -> str:
    from app.storage import local as storage

    return str(storage.get_file(uid))


def test_metric_deltas_report_both_sides_and_b_minus_a() -> None:
    uid_a = _upload("1CRN.pdb")
    uid_b = _upload("parity_multichain.pdb")
    summary_a, summary_b = registry_summary(uid_a), registry_summary(uid_b)
    rows = compare.metric_deltas(summary_a, summary_b, _analytics(uid_a), _analytics(uid_b))

    by_key = {row.key: row for row in rows}
    assert set(by_key) == {"chain_count", "residue_count", "atom_count", "molecular_weight"}
    assert by_key["residue_count"].a == float(summary_a.residue_count)
    assert by_key["residue_count"].b == float(summary_b.residue_count)
    for row in rows:
        assert row.delta == pytest.approx(row.b - row.a, abs=0.01), row.key
    assert by_key["molecular_weight"].unit == "Da"


def test_chain_lengths_pair_longest_first_and_keep_unmatched_chains() -> None:
    """A one-chain prediction against a multi-chain crystal form.

    The extra chains must stay visible as rows with a null A side, not vanish.
    """
    uid_a = _upload("1CRN.pdb")            # 1 chain
    uid_b = _upload("parity_multichain.pdb")  # several
    rows = compare.chain_length_pairs(_analytics(uid_a), _analytics(uid_b))

    analytics_b = _analytics(uid_b)
    assert len(rows) == max(1, len(analytics_b.chain_lengths))
    assert rows[0].chain_a == "A" and rows[0].length_a == 46
    assert rows[0].delta == rows[0].length_b - rows[0].length_a
    # Descending by length, and unmatched rows carry a null A side + null delta.
    lengths_b = [r.length_b for r in rows if r.length_b is not None]
    assert lengths_b == sorted(lengths_b, reverse=True)
    for row in rows[1:]:
        assert row.chain_a is None and row.length_a is None and row.delta is None


def test_composition_covers_every_standard_amino_acid_with_percentage_deltas() -> None:
    uid_a = _upload("1CRN.pdb")
    uid_b = _upload("parity_multichain.pdb")
    rows = compare.composition_deltas(_analytics(uid_a), _analytics(uid_b))

    assert len(rows) == 20
    assert [r.aa for r in rows] == sorted(r.aa for r in rows)
    for row in rows:
        assert row.delta_percent == pytest.approx(row.percent_b - row.percent_a, abs=0.01)
    cys = next(r for r in rows if r.aa == "C")
    assert cys.count_a == 6  # crambin's six cysteines


def test_secondary_structure_delta_carries_both_availability_flags() -> None:
    """`parity_multichain.pdb` declares no HELIX/SHEET; 1CRN declares four.

    Both orderings are checked: a flag that is read off one side and hard-coded
    on the other passes a single-ordering test, and would then tell the UI that
    an AlphaFold model's placeholder all-coil split was a measurement.
    """
    annotated = _upload("1CRN.pdb")
    unannotated = _upload("parity_multichain.pdb")

    delta = compare.secondary_structure_delta(_analytics(annotated), _analytics(unannotated))
    assert delta.available_a is True
    assert delta.available_b is False
    assert delta.helix_delta == pytest.approx(delta.helix_b - delta.helix_a, abs=1e-4)
    assert delta.sheet_delta == pytest.approx(delta.sheet_b - delta.sheet_a, abs=1e-4)
    assert delta.coil_delta == pytest.approx(delta.coil_b - delta.coil_a, abs=1e-4)

    flipped = compare.secondary_structure_delta(_analytics(unannotated), _analytics(annotated))
    assert flipped.available_a is False
    assert flipped.available_b is True
    assert flipped.helix_a == 0.0 and flipped.helix_b == delta.helix_a
    assert flipped.helix_delta == pytest.approx(-delta.helix_delta, abs=1e-4)


# --------------------------------------------------------------------------- #
# POST /api/compare                                                            #
# --------------------------------------------------------------------------- #


def test_compare_endpoint_returns_the_full_payload() -> None:
    uid_a = _upload("1CRN.pdb")
    uid_b = _upload("1CRN_ss.cif")
    res = client.post("/api/compare", json={"a": uid_a, "b": uid_b})
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["a"]["id"] == uid_a and body["b"]["id"] == uid_b
    assert body["a"]["file_format"] == "pdb" and body["b"]["file_format"] == "mmcif"
    assert len(body["metrics"]) == 4
    assert len(body["composition"]) == 20
    assert body["chain_lengths"][0]["delta"] == 0

    # Same molecule in two file formats: identical sequence, zero RMSD.
    assert body["alignment"]["identity_percent"] == 100.0
    assert body["alignment"]["match_line"] == "|" * 46
    assert body["superposition"]["rmsd"] == pytest.approx(0.0, abs=1e-3)
    assert body["superposition"]["atom_pairs"] == 46


def test_compare_endpoint_404s_name_the_side_that_is_missing() -> None:
    """Two ids in one request: a bare "not found" leaves the client guessing.

    `missing` is a well-formed uid that is simply not registered, so this
    exercises the registry miss rather than the uid-format rejection — the two
    404s come from different branches and both have to name their side.
    """
    uid = _upload("1CRN.pdb")
    missing = uuid.uuid4().hex
    assert missing != uid
    assert client.post("/api/compare", json={"a": missing, "b": uid}).json()["detail"] == (
        "Protein A not found"
    )
    assert client.post("/api/compare", json={"a": uid, "b": missing}).json()["detail"] == (
        "Protein B not found"
    )


def test_compare_endpoint_404s_name_the_side_with_a_malformed_uid() -> None:
    """The other 404 branch: the uid never reaches the registry at all."""
    uid = _upload("1CRN.pdb")
    assert client.post("/api/compare", json={"a": "not-a-uid", "b": uid}).json()["detail"] == (
        "Protein A not found"
    )
    assert client.post("/api/compare", json={"a": uid, "b": "not-a-uid"}).json()["detail"] == (
        "Protein B not found"
    )


def test_compare_endpoint_rejects_a_malformed_uid_as_not_found() -> None:
    uid = _upload("1CRN.pdb")
    res = client.post("/api/compare", json={"a": uid, "b": "../../etc/passwd"})
    assert res.status_code == 404


def test_compare_endpoint_honours_an_explicit_chain_selection() -> None:
    uid_a = _upload("1CRN.pdb")
    uid_b = _upload("parity_multichain.pdb")
    summary_b = registry_summary(uid_b)
    shortest = min(summary_b.chains, key=lambda c: (c.residue_count, c.label))

    res = client.post(
        "/api/compare", json={"a": uid_a, "b": uid_b, "chain_b": shortest.label}
    )
    assert res.status_code == 200, res.text
    assert res.json()["alignment"]["chain_b"] == shortest.label
    assert res.json()["alignment"]["length_b"] == shortest.residue_count


def test_compare_endpoint_explains_an_unknown_chain_instead_of_failing() -> None:
    """The metric diff is still worth serving when only the alignment is impossible."""
    uid_a = _upload("1CRN.pdb")
    uid_b = _upload("1CRN_ss.cif")
    res = client.post("/api/compare", json={"a": uid_a, "b": uid_b, "chain_b": "Z"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["alignment"] is None
    assert body["superposition"] is None
    assert "no chain Z" in body["alignment_note"]
    assert "available: A" in body["alignment_note"]
    # Layer 1 survives layer 2's absence.
    assert len(body["metrics"]) == 4
