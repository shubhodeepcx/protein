"""Pydantic models for the P7 comparison view (spec A3).

Everything here is a *diff* between two proteins that are already stored and
parsed. Both sides are always reported alongside the delta, so the client never
has to re-derive one from the other — and so a delta of zero is visibly
"identical" rather than "missing".

Delta convention, used without exception: ``delta = b - a``. Positive means B
has more of it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    """Body for ``POST /api/compare``."""

    a: str = Field(..., description="Storage uid of the first protein.")
    b: str = Field(..., description="Storage uid of the second protein.")
    chain_a: str | None = Field(
        None,
        description=(
            "Chain label of A to align and superpose. Defaults to A's longest "
            "chain — the same 'primary chain' the analytics endpoint profiles."
        ),
    )
    chain_b: str | None = Field(
        None, description="Chain label of B to align and superpose. Defaults to B's longest."
    )


class ProteinRef(BaseModel):
    """Identity of one side of the comparison.

    A deliberately narrow projection of ``ProteinSummary``: enough for the
    comparison header and for the client to load the structure into a viewer,
    without duplicating the per-chain sequences the client already has.
    """

    id: str
    source: Literal["uploaded", "rcsb", "alphafold", "uniprot"]
    source_id: str | None
    name: str | None
    organism: str | None
    file_url: str
    file_format: Literal["pdb", "mmcif"]
    has_plddt: bool


class MetricDelta(BaseModel):
    """One scalar metric on both proteins, plus ``b - a``."""

    key: str = Field(..., description="Stable machine key, e.g. 'molecular_weight'.")
    label: str = Field(..., description="Display label, e.g. 'Molecular weight'.")
    unit: str | None = Field(None, description="Unit for display, e.g. 'Da'. None when unitless.")
    a: float
    b: float
    delta: float = Field(..., description="b - a.")


class ChainLengthPair(BaseModel):
    """One row of the per-chain length diff.

    Chains are paired by descending length, not by label: two structures of the
    same protein routinely label their chains differently (a crystal form's
    A/B/C/D against a prediction's single A), and pairing longest-with-longest
    is the only correspondence that survives that. ``rank`` is the 0-based
    position in that ordering. A side with fewer chains reports ``None`` for its
    half of the row rather than dropping the row, so an extra chain on one side
    stays visible.
    """

    rank: int
    chain_a: str | None
    length_a: int | None
    chain_b: str | None
    length_b: int | None
    delta: int | None = Field(None, description="length_b - length_a, None when a side is absent.")


class CompositionDelta(BaseModel):
    """One amino acid's abundance on both sides.

    ``delta_percent`` (not ``delta_count``) is the comparable figure: two
    structures of very different size differ in every raw count, and only the
    percentages say whether the *composition* differs.
    """

    aa: str
    label: str
    count_a: int
    count_b: int
    percent_a: float
    percent_b: float
    delta_percent: float


class SecondaryStructureDelta(BaseModel):
    """Helix / sheet / coil fractions on both sides.

    ``available_a`` / ``available_b`` carry ``SecondaryStructurePercentages.available``
    through unchanged. When either is False that side's split is an all-coil
    placeholder — an AlphaFold model declares no secondary structure — and the
    deltas on this row are meaningless. The flags are here so the client can say
    so instead of drawing a 55-point helix difference that is really an absence.
    """

    helix_a: float
    helix_b: float
    helix_delta: float
    sheet_a: float
    sheet_b: float
    sheet_delta: float
    coil_a: float
    coil_b: float
    coil_delta: float
    available_a: bool
    available_b: bool


class SequenceAlignment(BaseModel):
    """Global pairwise alignment of one chain from each protein.

    Three denominators are reported because they answer different questions and
    are routinely confused:

    * ``identity_percent`` — identities over ``alignment_length``, the figure
      EMBOSS ``needle`` prints. Terminal gaps are in the denominator, so a short
      construct against a full-length model scores low here even when the
      overlapping region matches perfectly.
    * ``identity_percent_aligned`` — identities over ``aligned_columns`` (columns
      where neither side is a gap). This is the "how similar is the shared part"
      number.
    * ``similarity_percent`` — similarities over ``alignment_length``. A column
      counts as similar when its BLOSUM62 score is positive, the '+' of a BLAST
      match line.

    ``X`` (the parser's placeholder for a non-standard residue) never counts as
    an identity or a similarity, including against another ``X``: two unknowns
    are not evidence of a match.
    """

    chain_a: str
    chain_b: str
    length_a: int
    length_b: int
    alignment_length: int = Field(..., description="Total columns, gaps included.")
    aligned_columns: int = Field(..., description="Columns where neither side is a gap.")
    identities: int
    similarities: int
    gap_columns: int
    identity_percent: float
    similarity_percent: float
    identity_percent_aligned: float
    score: float = Field(..., description="Raw BLOSUM62 + affine-gap alignment score.")
    aligned_a: str = Field(..., description="Chain A's row, '-' for gaps.")
    aligned_b: str = Field(..., description="Chain B's row, '-' for gaps.")
    match_line: str = Field(
        ...,
        description="'|' identity, '+' similar-not-identical, ' ' otherwise. Same length as the rows.",
    )


class Superposition(BaseModel):
    """Least-squares superposition RMSD over alignment-paired CA atoms.

    The residue pairing comes from :class:`SequenceAlignment` — column by column,
    keeping only columns where both sides are a real residue with a CA atom. The
    RMSD is therefore only as trustworthy as that alignment, which is why
    ``identity_percent`` travels with it and ``caveat`` is set when the alignment
    is too weak to pair residues on.
    """

    chain_a: str
    chain_b: str
    rmsd: float = Field(..., description="Angstroms, over the paired CA atoms.")
    atom_pairs: int = Field(..., description="CA atom pairs the fit used.")
    residue_pairs: int = Field(
        ..., description="Alignment columns with a real residue on both sides, CA or not."
    )
    identity_percent: float = Field(
        ..., description="Identity of the alignment that produced the pairing."
    )
    caveat: str | None = Field(
        None, description="Set when the RMSD is real but should not be read at face value."
    )


class CompareResponse(BaseModel):
    """Full comparison payload for two stored proteins."""

    a: ProteinRef
    b: ProteinRef
    metrics: list[MetricDelta]
    chain_lengths: list[ChainLengthPair]
    composition: list[CompositionDelta]
    secondary_structure: SecondaryStructureDelta
    alignment: SequenceAlignment | None
    alignment_note: str = Field(
        ..., description="Why there is no alignment, or which chains were aligned."
    )
    superposition: Superposition | None
    superposition_note: str = Field(
        ..., description="Why there is no RMSD, or what the fit was computed over."
    )
