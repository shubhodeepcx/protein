"""A1 — AlphaFold confidence analysis: pLDDT bands, low-confidence regions, PAE.

Split the same way P6/P9 split theirs: everything in this module except
`pae_matrix_for` is a **pure function** over already-parsed inputs, so the whole
projection is testable offline. The single I/O helper wraps
`AlphaFoldClient.fetch_pae` and owns the cache.

Three things shaped this module.

1. **pLDDT is read from the file we already stored, not from the AlphaFold
   API.** AlphaFold writes the per-residue pLDDT into the B-factor column, so a
   structure that was uploaded by hand — an AlphaFold model a user downloaded
   themselves, with no accession to look anything up by — still gets full band
   and region analysis. The API's own `fractionPlddt*` fields would only work
   for entries we imported, and they carry no positions, so they can say *how
   much* is disordered but never *where*.

2. **PAE and pLDDT run in opposite directions.** pLDDT is a confidence, 0-100,
   high is good. PAE is an error in Angstroms, low is good. Every threshold and
   every scale in this feature is one or the other, never both, and the
   direction is pinned by tests on both sides of the wire.

3. **Absence is stated, never drawn.** An experimental structure has no pLDDT
   and no PAE. It gets a 200 with `has_plddt: false` and a `note` — the same
   treatment P10 gave the secondary-structure donut after an all-coil
   placeholder shipped looking like a measurement.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from app.models.confidence import (
    BandKey,
    ConfidenceResponse,
    LowConfidenceRegion,
    PaeMatrix,
    PlddtBand,
)
from app.models.protein import ProteinSummary
from app.services.cache import TTLCache
from app.services.external import SourceNotFoundError, SourceUnavailableError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Bio.PDB.Structure import Structure

    from app.services.alphafold import AlphaFoldClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Band thresholds — AlphaFold DB's published convention.
#
# Very high > 90, confident 70-90, low 50-70, very low < 50. The edges are
# treated as half-open going up (a residue at exactly 90.0 is very high, at
# exactly 70.0 is confident) so every value between 0 and 100 lands in exactly
# one band and the four counts always sum to the residue count.
#
# Below 50 is a *different claim* from "uncertain": AlphaFold's own guidance is
# that sub-50 pLDDT frequently marks intrinsic disorder rather than a badly
# predicted fold, which is why `likely_disordered` exists as its own flag.
# ---------------------------------------------------------------------------
VERY_HIGH_MIN = 90.0
CONFIDENT_MIN = 70.0
LOW_MIN = 50.0

#: A residue counts as low confidence below this. Also the region threshold —
#: one constant, so the band table and the region list can never disagree.
LOW_CONFIDENCE_THRESHOLD = CONFIDENT_MIN

_BAND_ORDER: tuple[BandKey, ...] = ("very_high", "confident", "low", "very_low")

_BAND_LABELS: dict[BandKey, str] = {
    "very_high": "Very high",
    "confident": "Confident",
    "low": "Low",
    "very_low": "Very low",
}

_BAND_EDGES: dict[BandKey, tuple[float, float]] = {
    "very_high": (VERY_HIGH_MIN, 100.0),
    "confident": (CONFIDENT_MIN, VERY_HIGH_MIN),
    "low": (LOW_MIN, CONFIDENT_MIN),
    "very_low": (0.0, LOW_MIN),
}

_BAND_DESCRIPTIONS: dict[BandKey, str] = {
    "very_high": "Backbone and side chains are expected to be modelled accurately.",
    "confident": "The backbone is expected to be modelled well; side chains less so.",
    "low": "Treat with caution — the fold here may be wrong.",
    "very_low": "Should not be interpreted as a fold. Often intrinsically disordered.",
}

# ---------------------------------------------------------------------------
# PAE display budget.
#
# The guard is on **cells**, because cells are the actual cost: they are what
# the browser paints and what the JSON body carries. It is deliberately not a
# residue count — a residue cap would refuse or silently clip a large protein,
# whereas a cell budget bins one instead and says by how much.
#
# 16,384 cells is 128 x 128. At full resolution that covers every protein up to
# 128 residues untouched; above that the matrix is binned and both `bin_size`
# and `resolution_label` travel with the data so the UI can say so. 16,384
# rounded floats serialise to roughly 100 KB.
# ---------------------------------------------------------------------------
MAX_PAE_CELLS = 16_384
MAX_PAE_SIDE = math.isqrt(MAX_PAE_CELLS)

#: Decimals kept per PAE cell. PAE is published to 2 decimals; keeping more
#: would inflate the body without adding information.
PAE_DECIMALS = 2

#: How many binned matrices to keep. Unlike a raw-matrix cache this is a real
#: memory bound: every entry is capped at `MAX_PAE_CELLS` floats (~525 KB as
#: Python lists), so 32 entries is ~17 MB whatever the proteins' sizes.
PAE_CACHE_MAXSIZE = 32

_PAE_CACHE: TTLCache[PaeMatrix] = TTLCache(maxsize=PAE_CACHE_MAXSIZE)


def clear_pae_cache() -> None:
    """Drop every cached binned matrix. Used by tests."""
    _PAE_CACHE.clear()


# ------------------------------------------------------------------ pLDDT


def band_for(plddt: float) -> BandKey:
    """The AlphaFold band one pLDDT value falls in.

    Half-open upwards: 90.0 is very high, 70.0 is confident, 50.0 is low.
    """
    if plddt >= VERY_HIGH_MIN:
        return "very_high"
    if plddt >= CONFIDENT_MIN:
        return "confident"
    if plddt >= LOW_MIN:
        return "low"
    return "very_low"


def extract_plddt(structure: "Structure") -> list[tuple[str, list[float]]]:
    """Per-residue pLDDT from the B-factor column, per chain, in file order.

    The residue filter mirrors `services/parser.py` exactly — first model,
    hetero-flag `" "` only — so ordinal *n* here is ordinal *n* in the sequence
    panel. This module never rewrites that mapping; it only reads alongside it.

    AlphaFold writes one pLDDT per residue onto every atom of that residue, so
    the CA value is the residue's score. The mean over the residue's atoms is
    the fallback for a residue with no CA (a truncated side chain, or a
    non-standard residue the parser kept as 'X').
    """
    chains: list[tuple[str, list[float]]] = []
    try:
        model = next(structure.get_models())
    except StopIteration:
        return chains

    for chain in model.get_chains():
        values: list[float] = []
        for residue in chain.get_residues():
            if residue.id[0] != " ":
                continue
            atoms = list(residue.get_atoms())
            if not atoms:
                continue
            ca = next((a for a in atoms if a.get_id() == "CA"), None)
            if ca is not None:
                values.append(float(ca.get_bfactor()))
            else:
                values.append(sum(float(a.get_bfactor()) for a in atoms) / len(atoms))
        if values:
            chains.append((str(chain.id), values))
    return chains


def summarise_bands(values: list[float]) -> list[PlddtBand]:
    """The four bands, always all four, with counts and fractions.

    Empty bands are kept rather than filtered: a legend that loses its 'Very
    low' row when there is none reads as though the band does not exist, and
    the reader cannot tell "zero" from "not measured".
    """
    total = len(values)
    counts: dict[BandKey, int] = {key: 0 for key in _BAND_ORDER}
    for value in values:
        counts[band_for(value)] += 1

    bands: list[PlddtBand] = []
    for key in _BAND_ORDER:
        low, high = _BAND_EDGES[key]
        bands.append(
            PlddtBand(
                key=key,
                label=_BAND_LABELS[key],
                min_plddt=low,
                max_plddt=high,
                residue_count=counts[key],
                fraction=(counts[key] / total) if total else 0.0,
                description=_BAND_DESCRIPTIONS[key],
            )
        )
    return bands


def _region_label(region: LowConfidenceRegion) -> str:
    span = (
        f"residue {region.start}"
        if region.length == 1
        else f"residues {region.start}-{region.end}"
    )
    plural = "" if region.length == 1 else "s"
    tail = (
        " — likely disordered, do not interpret as a fold"
        if region.likely_disordered
        else " — treat the fold here with caution"
    )
    return (
        f"Chain {region.chain_id} {span} "
        f"({region.length} residue{plural}, mean pLDDT {region.mean_plddt:.1f}, "
        f"lowest {region.min_plddt:.1f}){tail}"
    )


def low_confidence_regions(
    chains: list[tuple[str, list[float]]],
    threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> list[LowConfidenceRegion]:
    """Every contiguous run of residues below `threshold`, chain by chain.

    Deliberately unfiltered and uncapped. A minimum run length would hide real
    single-residue dips, and a cap on the number of regions would silently
    truncate exactly the disordered proteins this analysis exists for. The
    worst realistic case — a run of length 1 every other residue across
    AlphaFold's 2,700-residue fragment limit — is about 1,350 regions, which is
    a bounded payload and a true statement about a genuinely strange model.
    """
    regions: list[LowConfidenceRegion] = []
    for label, values in chains:
        start: int | None = None
        run: list[float] = []
        for index, value in enumerate(values, start=1):
            if value < threshold:
                if start is None:
                    start = index
                run.append(value)
                continue
            if start is not None:
                regions.append(_make_region(label, start, run))
                start, run = None, []
        if start is not None:
            regions.append(_make_region(label, start, run))
    return regions


def _make_region(chain_id: str, start: int, run: list[float]) -> LowConfidenceRegion:
    worst = min(run)
    region = LowConfidenceRegion(
        chain_id=chain_id,
        start=start,
        end=start + len(run) - 1,
        length=len(run),
        mean_plddt=sum(run) / len(run),
        min_plddt=worst,
        band=band_for(worst),
        likely_disordered=worst < LOW_MIN,
    )
    region.label = _region_label(region)
    return region


# -------------------------------------------------------------------- PAE


def bin_size_for(residue_count: int, max_cells: int = MAX_PAE_CELLS) -> int:
    """Residues per display cell so the binned matrix fits `max_cells`.

    1 whenever the full matrix already fits — a small protein is never
    degraded. Otherwise the smallest bin that fits, so nothing is thrown away
    that did not have to be.
    """
    if residue_count <= 0 or max_cells <= 0:
        return 1
    side = math.isqrt(max_cells)
    if side < 1:
        return 1
    return max(1, math.ceil(residue_count / side))


def downsample_pae(
    values: list[list[float]], max_cells: int = MAX_PAE_CELLS
) -> tuple[list[list[float]], int]:
    """Bin a full PAE matrix down to at most `max_cells` cells.

    Returns `(binned, bin_size)`. Each output cell is the **mean** PAE over its
    `bin_size x bin_size` block of residue pairs — the standard reduction for
    PAE, and the one that preserves the block structure a reader is looking
    for. It is a mean and not a maximum, so a single bad pair inside a
    confident domain does not repaint the whole block; `bin_size` travels with
    the matrix so the reader knows what a cell stands for.

    Nothing is ever dropped: the final block is short when N is not a multiple
    of `bin_size`, and it is averaged over the residues it actually has.
    """
    side = len(values)
    bin_size = bin_size_for(side, max_cells)
    if bin_size <= 1:
        return [[round(cell, PAE_DECIMALS) for cell in row] for row in values], 1

    out_side = math.ceil(side / bin_size)
    binned: list[list[float]] = []
    for bi in range(out_side):
        row_start = bi * bin_size
        row_end = min(row_start + bin_size, side)
        out_row: list[float] = []
        for bj in range(out_side):
            col_start = bj * bin_size
            col_end = min(col_start + bin_size, side)
            total = 0.0
            count = 0
            for row in values[row_start:row_end]:
                for cell in row[col_start:col_end]:
                    total += cell
                    count += 1
            out_row.append(round(total / count, PAE_DECIMALS) if count else 0.0)
        binned.append(out_row)
    return binned, bin_size


def resolution_label(residue_count: int, size: int, bin_size: int) -> str:
    """One line naming the resolution, for display beside the heatmap."""
    if bin_size <= 1:
        return (
            f"Full resolution — one cell per residue pair "
            f"({size} x {size} cells, {residue_count} residues)."
        )
    return (
        f"Binned {bin_size}x — each cell is the mean predicted aligned error over a "
        f"{bin_size} x {bin_size} block of residue pairs "
        f"({residue_count} residues shown as {size} x {size} cells)."
    )


def build_pae_matrix(
    values: list[list[float]],
    max_error: float,
    source_url: str = "",
    max_cells: int = MAX_PAE_CELLS,
) -> PaeMatrix:
    """Project a full PAE matrix onto the wire model, binned and self-describing."""
    residue_count = len(values)
    if residue_count == 0:
        return unavailable_pae("AlphaFold returned an empty PAE matrix.")
    binned, bin_size = downsample_pae(values, max_cells)
    size = len(binned)
    return PaeMatrix(
        available=True,
        residue_count=residue_count,
        size=size,
        bin_size=bin_size,
        downsampled=bin_size > 1,
        max_cells=max_cells,
        aggregation="mean" if bin_size > 1 else "none",
        max_error=max_error,
        resolution_label=resolution_label(residue_count, size, bin_size),
        values=binned,
        source_url=source_url,
    )


def unavailable_pae(reason: str) -> PaeMatrix:
    """A PAE block that says why it is empty. Never a zeroed matrix."""
    return PaeMatrix(available=False, unavailable_reason=reason, max_cells=MAX_PAE_CELLS)


async def pae_matrix_for(
    accession: str, client: "AlphaFoldClient", max_cells: int = MAX_PAE_CELLS
) -> PaeMatrix:
    """Fetch + bin the PAE for one accession, or explain why there is none.

    The only I/O in this module, and the only place that catches: PAE is a
    supplement to the pLDDT analysis, so an AlphaFold outage must degrade this
    one block rather than fail the whole endpoint. Every failure returns a
    `PaeMatrix` carrying a reason a reader can act on.
    """
    key = f"{accession}:{max_cells}"
    cached = _PAE_CACHE.get(key)
    if cached is not None:
        return cached

    try:
        document = await client.fetch_pae(accession)
    except SourceNotFoundError as exc:
        logger.info("No PAE for %s: %s", accession, exc)
        return unavailable_pae(
            f"AlphaFold publishes no predicted aligned error for {accession}."
        )
    except SourceUnavailableError as exc:
        logger.warning("PAE unavailable for %s: %s", accession, exc)
        return unavailable_pae(
            f"Could not read the AlphaFold predicted aligned error for {accession}: "
            f"{exc}"
        )

    matrix = build_pae_matrix(
        document.values, document.max_error, document.source_url, max_cells
    )
    if matrix.available:
        _PAE_CACHE.put(key, matrix)
    return matrix


# ----------------------------------------------------------------- assembly


def not_applicable(uid: str, note: str) -> ConfidenceResponse:
    """The response for a structure that carries no pLDDT at all.

    Every list stays empty and `has_plddt` stays false, so nothing downstream
    can mistake a default for a measurement. The note is the message.
    """
    return ConfidenceResponse(
        id=uid,
        has_plddt=False,
        note=note,
        low_confidence_threshold=LOW_CONFIDENCE_THRESHOLD,
        pae=unavailable_pae(note),
    )


def build_confidence(
    uid: str,
    summary: ProteinSummary,
    chains: list[tuple[str, list[float]]],
    pae: PaeMatrix,
    accession: str | None = None,
    note: str = "",
) -> ConfidenceResponse:
    """Assemble the full confidence response from already-extracted pLDDT."""
    values = [value for _, chain_values in chains for value in chain_values]
    if not values:
        return not_applicable(
            uid,
            "This structure is marked as an AlphaFold model but carries no per-residue "
            "confidence values, so no pLDDT analysis is possible.",
        )

    regions = low_confidence_regions(chains)
    low_count = sum(region.length for region in regions)

    warnings: list[str] = []
    # The pLDDT walk and the parser's sequence walk must see the same residues.
    # If they ever disagree, every residue range in `low_confidence_regions`
    # points somewhere slightly wrong — so say so instead of shipping ranges
    # that quietly do not line up with the sequence panel.
    scored = {label: len(chain_values) for label, chain_values in chains}
    for chain in summary.chains:
        expected = chain.residue_count
        actual = scored.get(chain.label)
        if actual is not None and actual != expected:
            warnings.append(
                f"Chain {chain.label}: scored {actual} residues but the sequence has "
                f"{expected}. Residue ranges below may be offset."
            )

    return ConfidenceResponse(
        id=uid,
        has_plddt=True,
        note=note,
        accession=accession,
        residue_count=len(values),
        mean_plddt=sum(values) / len(values),
        bands=summarise_bands(values),
        low_confidence_regions=regions,
        low_confidence_residue_count=low_count,
        low_confidence_fraction=low_count / len(values),
        low_confidence_threshold=LOW_CONFIDENCE_THRESHOLD,
        pae=pae,
        warnings=warnings,
    )
