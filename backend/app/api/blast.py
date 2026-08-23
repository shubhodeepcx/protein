"""BLAST submit + poll endpoints (P8).

The project's first asynchronous feature, and the only place its request shape
differs from everything else:

* `POST /api/blast` submits and returns a job id **immediately**. It never
  waits for the search — a BLAST run takes 30 s to several minutes, and a
  request held open that long is a request that times out somewhere.
* `GET /api/blast/{job_id}` reports status, and carries results only once the
  status is FINISHED. It makes at most one upstream round trip per call and
  none at all once the job is in a terminal state
  (`services/blast_jobs.BlastJobRegistry.poll`).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.blast import (
    BlastJobStatus,
    BlastSubmitRequest,
    BlastSubmitResponse,
    normalise_sequence,
)
from app.models.protein import ProteinSummary
from app.services import blast_jobs, registry
from app.services.blast import BlastRequestRejected, validate_job_id
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.storage import local as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blast", tags=["blast"])


def _query_from_summary(
    summary: ProteinSummary, chain_id: str | None
) -> tuple[str, str]:
    """Pick the chain to BLAST and return `(sequence, human-readable source)`.

    Defaults to the longest chain, matching how `analytics` already picks the
    "primary" chain for the hydrophobicity profile — one convention, not two.
    """
    if not summary.chains:
        raise HTTPException(
            status_code=400,
            detail="This structure has no protein chains to search with.",
        )
    if chain_id:
        wanted = chain_id.strip().upper()
        for chain in summary.chains:
            if chain.label.upper() == wanted:
                return chain.sequence, f"{summary.source_id or summary.id} chain {chain.label}"
        available = ", ".join(c.label for c in summary.chains)
        raise HTTPException(
            status_code=400,
            detail=f"No chain {chain_id!r} in this structure. Available: {available}.",
        )
    chain = max(summary.chains, key=lambda c: c.residue_count)
    return chain.sequence, f"{summary.source_id or summary.id} chain {chain.label}"


@router.post("", response_model=BlastSubmitResponse, status_code=202)
async def submit_blast(payload: BlastSubmitRequest) -> BlastSubmitResponse:
    """Submit a BLAST search. Returns a job id; does not wait for results.

    202 rather than 200: the work has been accepted, not completed.
    """
    if payload.protein_id:
        try:
            storage.validate_uid(payload.protein_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Protein not found") from exc
        summary = registry.get(payload.protein_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Protein not found")
        raw_sequence, query_source = _query_from_summary(summary, payload.chain_id)
    else:
        raw_sequence = payload.sequence or ""
        query_source = "pasted sequence"

    try:
        sequence = normalise_sequence(raw_sequence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    jobs = blast_jobs.get_registry()
    try:
        job_id = await jobs.client.submit(
            sequence=sequence,
            program=payload.program,
            database=payload.database,
            stype=payload.query_type,
            exp=payload.exp,
            alignments=payload.alignments,
            scores=payload.scores,
            matrix=payload.matrix,
            filter_low_complexity=payload.filter_low_complexity,
        )
    except BlastRequestRejected as exc:
        # EBI's own words about why the parameters are wrong; retrying as-is
        # would fail identically, so this is a 400, not a 502.
        logger.info("EBI rejected a BLAST submission: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SourceUnavailableError as exc:
        logger.warning("BLAST submission could not reach EBI: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach EBI to submit the BLAST search. Try again.",
        ) from exc

    record = jobs.register(
        job_id,
        program=payload.program,
        database=payload.database,
        query_length=len(sequence),
        query_source=query_source,
    )
    return BlastSubmitResponse(
        job_id=record.job_id,
        status=record.status,
        program=record.program,
        database=record.database,
        query_length=record.query_length,
        query_source=record.query_source,
        submitted_at=record.submitted_at,
        poll_url=f"/api/blast/{record.job_id}",
    )


@router.get("/{job_id}", response_model=BlastJobStatus)
async def get_blast_job(job_id: str) -> BlastJobStatus:
    """Poll one BLAST job. Never blocks; results appear once status is FINISHED."""
    try:
        safe_id = validate_job_id(job_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="BLAST job not found") from exc

    jobs = blast_jobs.get_registry()
    record = await jobs.poll(safe_id)
    if record is None:
        # Either never submitted here, or the server restarted. Say which is
        # possible rather than implying the id was malformed.
        raise HTTPException(
            status_code=404,
            detail="This server has no record of that BLAST job. It may have expired "
            "or been submitted before a restart — run the search again.",
        )
    return record.to_status()
