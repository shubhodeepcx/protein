"""``POST /api/compare`` — side-by-side comparison of two stored proteins (P7 / spec A3).

Pure local computation: everything compared here is already on disk and already
parsed. No external service is contacted, so this endpoint cannot degrade the
way `search` and `annotations` can.

The response is assembled in three layers, each of which can be absent without
taking the others down:

1. the metric / composition / secondary-structure diff, which always exists;
2. the pairwise sequence alignment, which needs one protein chain on each side;
3. the superposition RMSD, which needs the alignment plus a residue pairing this
   module can verify.

A failure in layer 3 leaves layers 1 and 2 intact and reports itself in
``superposition_note``, rather than 500-ing the whole comparison.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.api.proteins import compute_analytics, parse_structure_for_analytics
from app.models.compare import (
    CompareRequest,
    CompareResponse,
    ProteinRef,
)
from app.models.protein import ChainInfo, ProteinSummary
from app.services import compare as compare_service
from app.services import registry
from app.storage import local as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])


def _protein_ref(summary: ProteinSummary) -> ProteinRef:
    return ProteinRef(
        id=summary.id,
        source=summary.source,
        source_id=summary.source_id,
        name=summary.name,
        organism=summary.organism,
        file_url=summary.file_url,
        file_format=summary.file_format,
        has_plddt=summary.has_plddt,
    )


def _load(uid: str, side: str) -> ProteinSummary:
    """The registered summary for `uid`, or a 404 naming which side failed.

    Naming the side matters: with two ids in one request, a bare "Protein not
    found" leaves the client unable to say which of its two links is stale.
    """
    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Protein {side} not found") from exc
    summary = registry.get(uid)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Protein {side} not found")
    return summary


def _build_comparison(
    summary_a: ProteinSummary,
    summary_b: ProteinSummary,
    request: CompareRequest,
) -> CompareResponse:
    """Do the whole comparison. Synchronous and CPU-bound — run in a threadpool."""
    path_a = storage.get_file(summary_a.id)
    path_b = storage.get_file(summary_b.id)

    analytics_a = compute_analytics(summary_a.id, summary_a, path_a)
    analytics_b = compute_analytics(summary_b.id, summary_b, path_b)

    alignment = None
    superposition = None
    superposition_note = "No superposition: it needs a sequence alignment first."

    chain_a = compare_service.primary_chain(summary_a, request.chain_a)
    chain_b = compare_service.primary_chain(summary_b, request.chain_b)

    if chain_a is None or chain_b is None:
        alignment_note = _missing_chain_note(summary_a, summary_b, request, chain_a, chain_b)
    else:
        try:
            alignment = compare_service.align_chains(chain_a, chain_b)
        except compare_service.AlignmentTooLargeError as exc:
            alignment_note = str(exc)
        else:
            alignment_note = (
                f"Aligned chain {chain_a.label} ({chain_a.residue_count} residues) against "
                f"chain {chain_b.label} ({chain_b.residue_count} residues), global "
                "BLOSUM62 alignment with free end gaps."
            )
            outcome = compare_service.superpose(
                parse_structure_for_analytics(path_a),
                parse_structure_for_analytics(path_b),
                alignment,
                chain_a,
                chain_b,
            )
            superposition = outcome.result
            superposition_note = outcome.note

    return CompareResponse(
        a=_protein_ref(summary_a),
        b=_protein_ref(summary_b),
        metrics=compare_service.metric_deltas(summary_a, summary_b, analytics_a, analytics_b),
        chain_lengths=compare_service.chain_length_pairs(analytics_a, analytics_b),
        composition=compare_service.composition_deltas(analytics_a, analytics_b),
        secondary_structure=compare_service.secondary_structure_delta(analytics_a, analytics_b),
        alignment=alignment,
        alignment_note=alignment_note,
        superposition=superposition,
        superposition_note=superposition_note,
    )


def _missing_chain_note(
    summary_a: ProteinSummary,
    summary_b: ProteinSummary,
    request: CompareRequest,
    chain_a: ChainInfo | None,
    chain_b: ChainInfo | None,
) -> str:
    """Say which side had no usable chain, and whether it was asked for by name."""
    parts: list[str] = []
    for side, summary, requested, resolved in (
        ("A", summary_a, request.chain_a, chain_a),
        ("B", summary_b, request.chain_b, chain_b),
    ):
        if resolved is not None:
            continue
        if requested is not None:
            available = ", ".join(c.label for c in summary.chains) or "none"
            parts.append(f"protein {side} has no chain {requested} (available: {available})")
        else:
            parts.append(f"protein {side} has no protein chains to align")
    return "No sequence alignment: " + "; ".join(parts) + "."


@router.post("", response_model=CompareResponse)
async def compare_proteins(request: CompareRequest) -> CompareResponse:
    """Compare two stored proteins: metrics, composition, alignment, RMSD."""
    summary_a = _load(request.a, "A")
    summary_b = _load(request.b, "B")

    try:
        return await run_in_threadpool(_build_comparison, summary_a, summary_b, request)
    except (FileNotFoundError, ValueError) as exc:
        # The summary is registered but its file is gone — the registry and the
        # storage directory have diverged. 404 is honest: this protein can no
        # longer be served, and no retry will change that.
        logger.warning("Structure file missing while comparing %s/%s: %s", request.a, request.b, exc)
        raise HTTPException(
            status_code=404, detail="Structure file missing for one of the proteins"
        ) from exc
