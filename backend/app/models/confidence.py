"""API models for A1 — AlphaFold confidence analysis.

Same posture as `models/annotations.py` and `models/complexes.py`: **every**
field carries a default, so an experimental structure — which has no pLDDT and
no PAE at all — still produces a valid `ConfidenceResponse` rather than a 4xx
the panel would have to interpret.

The one rule this module exists to enforce is that *absence is stated, never
drawn*. `has_plddt: false` and `pae.available: false` each carry a prose reason,
and the frontend is expected to render the reason instead of an empty or zeroed
picture. P10's secondary-structure donut and P7's comparison warning set that
precedent after a placeholder shipped once looking like a measurement.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BandKey = Literal["very_high", "confident", "low", "very_low"]


class PlddtBand(BaseModel):
    """One AlphaFold confidence band and how much of the model falls in it.

    The band edges are AlphaFold's published convention: very high above 90,
    confident 70-90, low 50-70, very low below 50. `min_plddt` / `max_plddt`
    are carried on the wire so the UI never has to hard-code the thresholds a
    second time — a duplicated 70 that drifts is exactly how a confident wrong
    picture gets shipped.
    """

    key: BandKey = Field(..., description="Stable band identifier.")
    label: str = Field("", description="Human-readable band name.")
    min_plddt: float = Field(0.0, description="Inclusive lower edge of the band.")
    max_plddt: float = Field(100.0, description="Exclusive upper edge (100 is inclusive).")
    residue_count: int = Field(0, description="Residues whose pLDDT falls in this band.")
    fraction: float = Field(0.0, description="Share of all scored residues, 0-1.")
    description: str = Field(
        "", description="What this band means for interpreting the model."
    )


class LowConfidenceRegion(BaseModel):
    """One contiguous stretch of residues below the confident threshold.

    `start` / `end` are 1-based ordinals **within the chain**, matching the
    numbering the sequence panel already uses (the parser's file-order walk).
    They are not `auth_seq_id` and must not be handed to Mol* directly.
    """

    chain_id: str = Field("", description="Chain label, e.g. 'A'.")
    start: int = Field(0, description="First residue ordinal in the run, 1-based.")
    end: int = Field(0, description="Last residue ordinal in the run, inclusive.")
    length: int = Field(0, description="Residues in the run.")
    mean_plddt: float = Field(0.0, description="Mean pLDDT across the run.")
    min_plddt: float = Field(0.0, description="Worst pLDDT in the run.")
    band: BandKey = Field(
        "low", description="Worst band the run reaches — 'low' or 'very_low'."
    )
    likely_disordered: bool = Field(
        False,
        description="True when the run dips below 50. AlphaFold's own guidance is "
        "that sub-50 pLDDT often marks intrinsic disorder rather than a merely "
        "uncertain fold, so this is a different claim from 'low confidence'.",
    )
    label: str = Field(
        "",
        description="Ready-to-read one-line warning, so the message never depends "
        "on the reader decoding a colour.",
    )


class PaeMatrix(BaseModel):
    """Predicted Aligned Error, binned for display, with its resolution stated.

    PAE is an N x N matrix of expected positional error in Angstroms: cell
    (i, j) is the expected error in residue j's position when the prediction is
    aligned on residue i. **Low is good** — the opposite direction from pLDDT.

    A full matrix is quadratic in residue count (1,000 residues is 1,000,000
    cells), so `values` is binned down to at most `max_cells` cells. `bin_size`,
    `size` and `resolution_label` describe exactly what was done, because an
    undeclared downsample is a quiet lie about the data.
    """

    available: bool = Field(
        False, description="False when there is no PAE to show. Then `values` is empty."
    )
    unavailable_reason: str = Field(
        "",
        description="Why there is no matrix — an experimental structure, an upload "
        "with no AlphaFold accession, an upstream failure. Empty when available.",
    )
    residue_count: int = Field(0, description="N — the side of the *full* matrix.")
    size: int = Field(0, description="Side of the returned (possibly binned) matrix.")
    bin_size: int = Field(
        1, description="Residues per returned cell. 1 means full resolution."
    )
    downsampled: bool = Field(False, description="True when `bin_size` > 1.")
    max_cells: int = Field(
        0, description="The cell budget `values` was binned to fit."
    )
    aggregation: Literal["mean", "none"] = Field(
        "none",
        description="How residues were combined into a cell. 'mean' when binned; "
        "'none' at full resolution.",
    )
    max_error: float = Field(
        0.0,
        description="Angstroms. AlphaFold's own ceiling for this entry — the top of "
        "the colour scale, so the scale is not rescaled per protein by accident.",
    )
    resolution_label: str = Field(
        "",
        description="One line stating the resolution in words, for display next to "
        "the heatmap.",
    )
    values: list[list[float]] = Field(
        default_factory=list, description="Row-major binned PAE, in Angstroms."
    )
    source_url: str = Field("", description="The AlphaFold PAE document this came from.")


class ConfidenceResponse(BaseModel):
    """Everything the Analytics tab needs to talk about model confidence."""

    id: str = Field(..., description="Protein UID.")
    has_plddt: bool = Field(
        False,
        description="False for an experimental structure. Then `bands`, "
        "`low_confidence_regions` and `pae` are all empty and `note` says why.",
    )
    note: str = Field(
        "",
        description="Prose explanation of what is and is not applicable to this "
        "structure. Always populated when something is missing.",
    )
    accession: str | None = Field(
        None, description="UniProt accession used for the PAE lookup, when there was one."
    )
    residue_count: int = Field(0, description="Residues carrying a pLDDT value.")
    mean_plddt: float | None = Field(
        None, description="Mean pLDDT over every scored residue, 0-100."
    )
    bands: list[PlddtBand] = Field(
        default_factory=list, description="The four bands, always all four when scored."
    )
    low_confidence_regions: list[LowConfidenceRegion] = Field(
        default_factory=list,
        description="Every contiguous run below the confident threshold, in chain "
        "then position order. Not truncated: a long list is a real finding.",
    )
    low_confidence_residue_count: int = Field(
        0, description="Residues below the confident threshold."
    )
    low_confidence_fraction: float = Field(
        0.0, description="Share of scored residues below the confident threshold, 0-1."
    )
    low_confidence_threshold: float = Field(
        70.0, description="The pLDDT below which a residue counts as low confidence."
    )
    pae: PaeMatrix = Field(default_factory=PaeMatrix, description="Binned PAE matrix.")
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal problems found while scoring."
    )
