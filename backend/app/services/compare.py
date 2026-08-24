"""Pairwise protein comparison (P7 / spec A3).

Pure computation only — no I/O and no network. Callers hand in objects that are
already parsed (``ProteinSummary``, ``AnalyticsResponse``, BioPython
``Structure``); every function here just diffs or aligns them.

Two things carry the correctness of this module:

* **The alignment is global with free end gaps** (EMBOSS ``needle``'s default),
  scored with BLOSUM62 and affine gaps. Free end gaps matter for A3's headline
  case: an AlphaFold model covers the whole UniProt sequence while the crystal
  form covers a construct, and charging for the overhang would push the aligner
  into shredding the core to avoid it.
* **The superposition pairs residues through that alignment**, and refuses
  rather than guesses whenever the pairing cannot be shown to be sound. A wrong
  RMSD is worse than no RMSD.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Bio import Align
from Bio.Align import substitution_matrices
from Bio.PDB.Superimposer import Superimposer

from app.models.analytics import AnalyticsResponse
from app.models.compare import (
    ChainLengthPair,
    CompositionDelta,
    MetricDelta,
    SecondaryStructureDelta,
    SequenceAlignment,
    Superposition,
)
from app.models.protein import ChainInfo, ProteinSummary

logger = logging.getLogger(__name__)

GAP = "-"

#: The parser writes 'X' for any residue outside the standard 20. Two X columns
#: are two unknowns, not a match, so X is excluded from identity and similarity.
UNKNOWN_RESIDUE = "X"

#: BLAST's blastp defaults. Affine gaps, so a long indel costs far less than the
#: many single-residue gaps a flat penalty would prefer.
_OPEN_GAP_SCORE = -11.0
_EXTEND_GAP_SCORE = -1.0

#: Global alignment is O(len_a * len_b). 4000 residues a side is ~16M cells,
#: which BioPython's C implementation does in well under a second; past that the
#: request stops being interactive, so it is refused with an explanation rather
#: than left to hang.
MAX_ALIGNABLE_RESIDUES = 4000

#: Three non-collinear points is the minimum for a determined 3D rotation. Fewer
#: pairs than this does not produce a weak RMSD, it produces a meaningless one.
MIN_SUPERPOSITION_ATOMS = 3

#: Below this identity, sequence alignment is in the "twilight zone" and the
#: residue correspondence it produces is not reliable enough to read the RMSD at
#: face value. The number is still returned — A3 explicitly wants similar folds
#: at low identity — but it is returned flagged.
TWILIGHT_ZONE_IDENTITY = 20.0

#: Thin fits are reported, but a five-atom RMSD is a different claim from a
#: five-hundred-atom one and should not look the same in the UI.
THIN_FIT_ATOM_PAIRS = 10


def build_aligner() -> Align.PairwiseAligner:
    """A global BLOSUM62 aligner with affine gaps and free end gaps.

    Public because A5 (`services/functional.py`) maps UniProt sequence
    positions onto structure residues through the *same* alignment model this
    module pairs residues with. Two aligners configured differently would let
    the comparison view and the functional-region view disagree about which
    residue of a construct a UniProt position corresponds to.
    """
    aligner = Align.PairwiseAligner()
    aligner.mode = "global"
    aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    aligner.open_gap_score = _OPEN_GAP_SCORE
    aligner.extend_gap_score = _EXTEND_GAP_SCORE
    # End gaps are free: an overhang is missing coverage, not a mismatch.
    # `end_gap_score` sets both sides at once and is the spelling that is stable
    # across BioPython versions — the per-side `target_`/`query_` names were
    # renamed to `end_insertion_score`/`end_deletion_score` in 1.88.
    aligner.end_gap_score = 0.0
    return aligner


class AlignmentTooLargeError(ValueError):
    """A chain is longer than :data:`MAX_ALIGNABLE_RESIDUES`."""


def primary_chain(summary: ProteinSummary, label: str | None = None) -> ChainInfo | None:
    """The chain to align on: the requested one, else the longest.

    Longest-chain is the same "primary chain" rule the analytics endpoint uses
    for its hydrophobicity profile, so the two surfaces never disagree about
    which chain represents a structure. Ties break on the chain label so the
    choice is stable across requests.
    """
    if not summary.chains:
        return None
    if label is not None:
        return next((c for c in summary.chains if c.label == label), None)
    return min(summary.chains, key=lambda c: (-c.residue_count, c.label))


def _percent(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def align_chains(chain_a: ChainInfo, chain_b: ChainInfo) -> SequenceAlignment:
    """Globally align two chains' sequences and score the result.

    Raises :class:`AlignmentTooLargeError` when either chain is over
    :data:`MAX_ALIGNABLE_RESIDUES`.
    """
    seq_a, seq_b = chain_a.sequence, chain_b.sequence
    if len(seq_a) > MAX_ALIGNABLE_RESIDUES or len(seq_b) > MAX_ALIGNABLE_RESIDUES:
        raise AlignmentTooLargeError(
            f"Chains of {len(seq_a)} and {len(seq_b)} residues exceed the "
            f"{MAX_ALIGNABLE_RESIDUES}-residue alignment limit."
        )

    aligner = build_aligner()
    matrix = aligner.substitution_matrix
    # `align` is lazy over every co-optimal path; [0] takes one, deterministically
    # for a given BioPython version. Co-optimal paths differ only in how they
    # arrange equal-scoring gaps, never in the score or the counts below.
    best = aligner.align(seq_a, seq_b)[0]
    row_a, row_b = str(best[0]), str(best[1])

    identities = similarities = aligned_columns = gap_columns = 0
    match_chars: list[str] = []
    for res_a, res_b in zip(row_a, row_b):
        if res_a == GAP or res_b == GAP:
            gap_columns += 1
            match_chars.append(" ")
            continue
        aligned_columns += 1
        if res_a == UNKNOWN_RESIDUE or res_b == UNKNOWN_RESIDUE:
            # An unknown residue is evidence of nothing, even against another
            # unknown. It occupies a column and counts as neither.
            match_chars.append(" ")
            continue
        if res_a == res_b:
            identities += 1
            similarities += 1
            match_chars.append("|")
        elif matrix[res_a, res_b] > 0:
            similarities += 1
            match_chars.append("+")
        else:
            match_chars.append(" ")

    columns = len(row_a)
    return SequenceAlignment(
        chain_a=chain_a.label,
        chain_b=chain_b.label,
        length_a=len(seq_a),
        length_b=len(seq_b),
        alignment_length=columns,
        aligned_columns=aligned_columns,
        identities=identities,
        similarities=similarities,
        gap_columns=gap_columns,
        identity_percent=_percent(identities, columns),
        similarity_percent=_percent(similarities, columns),
        identity_percent_aligned=_percent(identities, aligned_columns),
        score=float(best.score),
        aligned_a=row_a,
        aligned_b=row_b,
        match_line="".join(match_chars),
    )


def paired_indices(aligned_a: str, aligned_b: str) -> list[tuple[int, int]]:
    """0-based sequence indices for every column with a residue on both sides.

    The two rows are read as one column stream: each non-gap character advances
    that side's index, and a column with no gap on either side emits the pair.
    This is the bridge from the sequence alignment to the residue objects, so it
    is the single place where an off-by-one would silently corrupt an RMSD.
    """
    pairs: list[tuple[int, int]] = []
    index_a = index_b = 0
    for res_a, res_b in zip(aligned_a, aligned_b):
        a_present = res_a != GAP
        b_present = res_b != GAP
        if a_present and b_present:
            pairs.append((index_a, index_b))
        if a_present:
            index_a += 1
        if b_present:
            index_b += 1
    return pairs


def polymer_residues(structure, chain_label: str) -> list:
    """Standard polymer residues of `chain_label` in model 1, in file order.

    This mirrors ``services/parser.py``'s chain walk exactly — first model, then
    ``residue.id[0] == " "`` to drop waters, ligands, and other heteroatoms — so
    that element *i* of this list is the residue that produced character *i* of
    ``ChainInfo.sequence``. ``test_compare.py`` pins that agreement against the
    parser itself; it is the assumption every paired CA atom rests on.
    """
    try:
        model = next(structure.get_models())
    except StopIteration:
        return []
    for chain in model.get_chains():
        if chain.id == chain_label:
            return [r for r in chain.get_residues() if r.id[0] == " "]
    return []


@dataclass(frozen=True)
class SuperpositionOutcome:
    """Either a fit or the reason there is none — never both, never neither."""

    result: Superposition | None
    note: str


def superpose(
    structure_a,
    structure_b,
    alignment: SequenceAlignment,
    chain_a: ChainInfo,
    chain_b: ChainInfo,
) -> SuperpositionOutcome:
    """Least-squares fit over CA atoms paired through `alignment`.

    Refuses, with a note explaining why, whenever the pairing cannot be shown to
    be sound:

    * either chain's residue list does not match the length of the sequence the
      alignment was computed on — that means this module and the parser disagree
      about which residues are polymer, and every pair after the first
      divergence would be off;
    * fewer than :data:`MIN_SUPERPOSITION_ATOMS` pairs survive, so the rotation
      is underdetermined.

    A low-identity alignment is *not* a refusal: A3 asks for similar folds at low
    sequence identity. It is returned with ``caveat`` set.
    """
    residues_a = polymer_residues(structure_a, chain_a.label)
    residues_b = polymer_residues(structure_b, chain_b.label)

    # The guard that makes the pairing checkable rather than assumed.
    if len(residues_a) != len(chain_a.sequence) or len(residues_b) != len(chain_b.sequence):
        logger.warning(
            "Residue/sequence length mismatch (A: %d vs %d, B: %d vs %d); skipping RMSD",
            len(residues_a),
            len(chain_a.sequence),
            len(residues_b),
            len(chain_b.sequence),
        )
        return SuperpositionOutcome(
            None,
            "Superposition skipped: the structure files' residues do not line up with the "
            "parsed sequences, so alignment columns could not be mapped to atoms safely.",
        )

    pairs = paired_indices(alignment.aligned_a, alignment.aligned_b)
    fixed = []
    moving = []
    for index_a, index_b in pairs:
        res_a = residues_a[index_a]
        res_b = residues_b[index_b]
        # A residue modelled without its backbone alpha carbon cannot be fitted;
        # dropping the pair is correct, guessing another atom is not.
        if "CA" not in res_a or "CA" not in res_b:
            continue
        fixed.append(res_a["CA"])
        moving.append(res_b["CA"])

    if len(fixed) < MIN_SUPERPOSITION_ATOMS:
        return SuperpositionOutcome(
            None,
            f"Superposition skipped: only {len(fixed)} alpha-carbon pair(s) could be matched "
            f"through the alignment, below the {MIN_SUPERPOSITION_ATOMS} needed to determine "
            "a rotation.",
        )

    fitter = Superimposer()
    # `set_atoms(fixed, moving)` computes the optimal rotation+translation and
    # its RMS. `apply()` is deliberately not called: nothing here writes back
    # transformed coordinates, so both input structures stay untouched.
    fitter.set_atoms(fixed, moving)
    rms = fitter.rms
    if rms is None:
        return SuperpositionOutcome(
            None, "Superposition skipped: the least-squares fit did not converge."
        )

    caveats: list[str] = []
    if alignment.identity_percent_aligned < TWILIGHT_ZONE_IDENTITY:
        caveats.append(
            f"sequence identity over the aligned region is only "
            f"{alignment.identity_percent_aligned}%, inside the twilight zone where "
            "alignment-based residue pairing is unreliable"
        )
    if len(fixed) < THIN_FIT_ATOM_PAIRS:
        caveats.append(f"the fit uses only {len(fixed)} atom pairs")

    return SuperpositionOutcome(
        Superposition(
            chain_a=chain_a.label,
            chain_b=chain_b.label,
            rmsd=round(float(rms), 3),
            atom_pairs=len(fixed),
            residue_pairs=len(pairs),
            identity_percent=alignment.identity_percent_aligned,
            caveat="; ".join(caveats).capitalize() + "." if caveats else None,
        ),
        f"Fitted {len(fixed)} alpha-carbon pairs from chain {chain_a.label} onto "
        f"chain {chain_b.label}, paired through the sequence alignment.",
    )


def metric_deltas(
    summary_a: ProteinSummary,
    summary_b: ProteinSummary,
    analytics_a: AnalyticsResponse,
    analytics_b: AnalyticsResponse,
) -> list[MetricDelta]:
    """The headline scalar diff: chains, residues, atoms, molecular weight."""
    rows = (
        ("chain_count", "Chains", None, float(analytics_a.chain_count), float(analytics_b.chain_count)),
        ("residue_count", "Residues", None, float(summary_a.residue_count), float(summary_b.residue_count)),
        ("atom_count", "Atoms", None, float(summary_a.atom_count), float(summary_b.atom_count)),
        (
            "molecular_weight",
            "Molecular weight",
            "Da",
            round(summary_a.molecular_weight, 2),
            round(summary_b.molecular_weight, 2),
        ),
    )
    return [
        MetricDelta(key=key, label=label, unit=unit, a=a, b=b, delta=round(b - a, 2))
        for key, label, unit, a, b in rows
    ]


def chain_length_pairs(
    analytics_a: AnalyticsResponse, analytics_b: AnalyticsResponse
) -> list[ChainLengthPair]:
    """Per-chain lengths paired longest-first — see :class:`ChainLengthPair`."""
    ranked_a = sorted(analytics_a.chain_lengths, key=lambda c: (-c.length, c.chain_id))
    ranked_b = sorted(analytics_b.chain_lengths, key=lambda c: (-c.length, c.chain_id))

    rows: list[ChainLengthPair] = []
    for rank in range(max(len(ranked_a), len(ranked_b))):
        left = ranked_a[rank] if rank < len(ranked_a) else None
        right = ranked_b[rank] if rank < len(ranked_b) else None
        rows.append(
            ChainLengthPair(
                rank=rank,
                chain_a=left.chain_id if left else None,
                length_a=left.length if left else None,
                chain_b=right.chain_id if right else None,
                length_b=right.length if right else None,
                delta=(right.length - left.length) if (left and right) else None,
            )
        )
    return rows


def composition_deltas(
    analytics_a: AnalyticsResponse, analytics_b: AnalyticsResponse
) -> list[CompositionDelta]:
    """Amino-acid composition on both sides, by percentage-point difference.

    ``analytics.composition`` always returns all 20 standard residues in the
    same alphabetical order, zeros included, so the two lists line up by index
    and every amino acid gets a row even when neither protein contains it.
    """
    by_aa_b = {entry.aa: entry for entry in analytics_b.composition}
    rows: list[CompositionDelta] = []
    for entry_a in analytics_a.composition:
        entry_b = by_aa_b.get(entry_a.aa)
        percent_b = entry_b.percent if entry_b else 0.0
        rows.append(
            CompositionDelta(
                aa=entry_a.aa,
                label=entry_a.label,
                count_a=entry_a.count,
                count_b=entry_b.count if entry_b else 0,
                percent_a=entry_a.percent,
                percent_b=percent_b,
                delta_percent=round(percent_b - entry_a.percent, 2),
            )
        )
    return rows


def secondary_structure_delta(
    analytics_a: AnalyticsResponse, analytics_b: AnalyticsResponse
) -> SecondaryStructureDelta:
    """Helix / sheet / coil fractions on both sides, with both availability flags."""
    ss_a = analytics_a.secondary_structure
    ss_b = analytics_b.secondary_structure
    return SecondaryStructureDelta(
        helix_a=ss_a.helix,
        helix_b=ss_b.helix,
        helix_delta=round(ss_b.helix - ss_a.helix, 4),
        sheet_a=ss_a.sheet,
        sheet_b=ss_b.sheet,
        sheet_delta=round(ss_b.sheet - ss_a.sheet, 4),
        coil_a=ss_a.coil,
        coil_b=ss_b.coil,
        coil_delta=round(ss_b.coil - ss_a.coil, 4),
        available_a=ss_a.available,
        available_b=ss_b.available,
    )
