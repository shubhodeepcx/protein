"""Job registry and polling *policy* for BLAST searches (P8).

Kept out of `services/blast.py` on purpose. That module is transport: one
method, one round trip. This module decides *whether* a round trip is needed
at all, which is what lets `GET /api/blast/{job_id}` answer immediately
instead of blocking a request thread for the minutes a BLAST search takes.

Three rules make up the policy:

1. **A terminal status is answered from memory.** FINISHED / FAILURE / ERROR /
   NOT_FOUND never change, so a poll on one costs zero upstream calls no
   matter how often the browser asks.
2. **Upstream polls are throttled.** A browser polling every 500 ms must not
   become 120 requests/minute at EBI. `MIN_UPSTREAM_POLL_SECONDS` is a floor on
   *our* traffic; the client still gets an immediate answer, just the previous
   one.
3. **Results are fetched exactly once.** The transition to FINISHED is the only
   moment `retrieve_json` is called; the parsed result is then part of the record.

`parse_result` is pure — a recorded EBI payload in, a `BlastResult` out, no I/O
— which is what makes the field mapping testable offline against a real
recorded response.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models.blast import (
    TERMINAL_STATUSES,
    BlastHit,
    BlastHsp,
    BlastJobStatus,
    BlastProgram,
    BlastResult,
    BlastStatus,
)
from app.services.blast import EBIBlastClient
from app.services.cache import TTLCache
from app.services.external import (
    ExternalSourceError,
    SourceNotFoundError,
    SourceUnavailableError,
    as_float,
    as_int,
)
from app.services.uniprot import normalise_accession

logger = logging.getLogger(__name__)

# Floor on how often we will ask EBI about one job. EBI's own reference client
# (webservice-clients/python/ncbiblast.py) sleeps 3s between checks; 2s is a
# slightly tighter floor that still cannot become a hammer.
MIN_UPSTREAM_POLL_SECONDS = 2.0

# Job records live long enough to survive the user navigating away and back,
# and are bounded by an LRU so the process cannot grow without limit. Each
# record holds a parsed result with no alignment strings (see `BlastHsp`), so
# even a 1000-hit search is a few hundred kB — 256 of them is a real memory
# bound, not a guess.
JOB_CACHE_MAXSIZE = 256
JOB_TTL_SECONDS = 24 * 3600.0

_STATUS_MESSAGES: dict[str, str] = {
    "QUEUED": "Queued at EBI, waiting for a free worker.",
    "RUNNING": "Running at EBI. Protein searches usually take 30 s to a few minutes.",
    "FINISHED": "Search complete.",
    "FAILURE": "EBI reported that the search failed. Check the query sequence and database.",
    "ERROR": "EBI reported an error for this job.",
    "NOT_FOUND": "EBI no longer has this job. Results expire after a few days — run it again.",
}

_KNOWN_STATUSES: frozenset[str] = frozenset(_STATUS_MESSAGES)


@dataclass
class BlastJobRecord:
    """Everything we know about one submitted job."""

    job_id: str
    program: BlastProgram
    database: str
    query_length: int
    query_source: str
    submitted_at: datetime
    status: BlastStatus = "QUEUED"
    poll_count: int = 0
    message: str = _STATUS_MESSAGES["QUEUED"]
    result: BlastResult | None = None
    last_upstream_poll: float | None = field(default=None, repr=False)

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def elapsed_seconds(self) -> float:
        return max(0.0, (_utcnow() - self.submitted_at).total_seconds())

    def to_status(self) -> BlastJobStatus:
        return BlastJobStatus(
            job_id=self.job_id,
            status=self.status,
            finished=self.finished,
            program=self.program,
            database=self.database,
            query_length=self.query_length,
            query_source=self.query_source,
            submitted_at=self.submitted_at,
            elapsed_seconds=round(self.elapsed_seconds(), 1),
            poll_count=self.poll_count,
            message=self.message,
            result=self.result,
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BlastJobRegistry:
    """In-memory job store plus the polling policy described in the module docstring.

    In-memory like `services/registry.py`: this resets on restart, and the
    persistence slice covers both together. A job id survives a page reload
    because the browser keeps it, not because we do.
    """

    def __init__(
        self,
        client: EBIBlastClient | None = None,
        *,
        cache: TTLCache[BlastJobRecord] | None = None,
        min_upstream_poll_seconds: float = MIN_UPSTREAM_POLL_SECONDS,
    ) -> None:
        self._client = client or EBIBlastClient()
        self._jobs: TTLCache[BlastJobRecord] = cache or TTLCache(
            maxsize=JOB_CACHE_MAXSIZE, ttl_seconds=JOB_TTL_SECONDS
        )
        self._min_poll_interval = min_upstream_poll_seconds

    @property
    def client(self) -> EBIBlastClient:
        return self._client

    def register(
        self,
        job_id: str,
        *,
        program: BlastProgram,
        database: str,
        query_length: int,
        query_source: str,
    ) -> BlastJobRecord:
        record = BlastJobRecord(
            job_id=job_id,
            program=program,
            database=database,
            query_length=query_length,
            query_source=query_source,
            submitted_at=_utcnow(),
        )
        self._jobs.put(job_id, record)
        return record

    def get(self, job_id: str) -> BlastJobRecord | None:
        return self._jobs.get(job_id)

    async def poll(self, job_id: str) -> BlastJobRecord | None:
        """Advance one job, making at most one upstream round trip.

        Returns None when the job id is unknown to *us* — a job EBI still has
        but this process never registered (e.g. after a restart) is a 404 here,
        because we would not know the program, database or query it was for.
        """
        record = self._jobs.get(job_id)
        if record is None:
            return None

        if record.finished:
            return record  # rule 1: terminal statuses never change

        now = time.monotonic()
        last = record.last_upstream_poll
        if last is not None and (now - last) < self._min_poll_interval:
            return record  # rule 2: throttle our traffic, not the client's

        record.last_upstream_poll = now
        record.poll_count += 1

        try:
            raw_status = await self._client.status(job_id)
        except SourceNotFoundError:
            _apply_status(record, "NOT_FOUND")
            return record
        except SourceUnavailableError as exc:
            # A transport blip is not a job failure: leave the job where it is
            # and let the next poll try again.
            logger.warning("BLAST status check for %s failed: %s", job_id, exc)
            record.message = "Could not reach EBI for a status update. Still trying."
            return record

        status = _normalise_status(raw_status)
        if status != raw_status:
            logger.warning(
                "BLAST job %s reported unrecognised status %r", job_id, raw_status
            )
        _apply_status(record, status)

        if status == "FINISHED":
            try:
                payload = await self._client.retrieve_json(job_id)
            except ExternalSourceError as exc:
                # The search itself succeeded — say so, and let the next poll
                # retry the download rather than losing the result.
                logger.warning("BLAST result download for %s failed: %s", job_id, exc)
                record.status = "RUNNING"
                record.message = (
                    "The search finished but the results could not be downloaded yet. "
                    "Still trying."
                )
                return record
            record.result = parse_result(payload)
            record.message = (
                f"Search complete — {record.result.hit_count} "
                f"hit{'' if record.result.hit_count == 1 else 's'}."
            )

        return record

    def clear(self) -> None:
        """Drop every registered job. Used by tests."""
        self._jobs.clear()

    def size(self) -> int:
        return len(self._jobs)


def _normalise_status(raw: str) -> BlastStatus:
    """Map an upstream token onto our vocabulary, defaulting unknowns to ERROR."""
    token = raw.strip().upper()
    if token in _KNOWN_STATUSES:
        return token  # type: ignore[return-value]
    return "ERROR"


def _apply_status(record: BlastJobRecord, status: BlastStatus) -> None:
    record.status = status
    record.message = _STATUS_MESSAGES[status]


# ---------------------------------------------------------------- projection


def parse_result(payload: dict[str, Any]) -> BlastResult:
    """Flatten an EBI NCBI BLAST JSON result into `BlastResult`. Pure.

    Written against a real recorded response (see
    `tests/fixtures/ebi_ncbiblast_result_P35858.json`, trimmed from EBI's own
    published `example_blastp.json`) rather than a hand-written approximation.
    """
    raw_hits = payload.get("hits")
    hits = [
        _hit(raw, index)
        for index, raw in enumerate(raw_hits if isinstance(raw_hits, list) else [], start=1)
        if isinstance(raw, dict)
    ]
    dbs = payload.get("dbs")
    databases = (
        [d["name"] for d in dbs if isinstance(d, dict) and isinstance(d.get("name"), str)]
        if isinstance(dbs, list)
        else []
    )
    return BlastResult(
        program=_text(payload.get("program")),
        version=_text(payload.get("version")),
        databases=databases,
        query_id=_text(payload.get("query_id")),
        query_definition=_text(payload.get("query_def")),
        query_length=as_int(payload.get("query_len")),
        hit_count=len(hits),
        hits=hits,
        started_at=_text(payload.get("start")),
        finished_at=_text(payload.get("end")),
    )


def _hit(raw: dict[str, Any], fallback_rank: int) -> BlastHit:
    hsps = [
        _hsp(h, i)
        for i, h in enumerate(_as_list(raw.get("hit_hsps")), start=1)
        if isinstance(h, dict)
    ]
    # Best by score, not `hsps[0]`. EBI orders HSPs by score today; a table that
    # silently reported a weaker alignment if that ever changed would be nearly
    # impossible to spot from the outside.
    best = max(hsps, key=lambda h: (h.score if h.score is not None else -1), default=None)
    accession = _text(raw.get("hit_acc")) or ""

    return BlastHit(
        rank=as_int(raw.get("hit_num")) or fallback_rank,
        accession=accession,
        entry_id=_text(raw.get("hit_id")),
        # `hit_uni_de` is the clean description; `hit_desc` appends OS=/OX=/GN=.
        description=_text(raw.get("hit_uni_de")) or _text(raw.get("hit_desc")),
        database=_text(raw.get("hit_db")),
        organism=_text(raw.get("hit_uni_os")) or _text(raw.get("hit_os")),
        gene=_text(raw.get("hit_uni_gn")),
        length=as_int(raw.get("hit_len")),
        url=_text(raw.get("hit_url")),
        uniprot_accession=_uniprot_accession(accession),
        identity_percent=best.identity_percent if best else None,
        expect=best.expect if best else None,
        score=best.score if best else None,
        bit_score=best.bit_score if best else None,
        align_length=best.align_length if best else None,
        gaps=best.gaps if best else None,
        hsps=hsps,
    )


def _hsp(raw: dict[str, Any], fallback_rank: int) -> BlastHsp:
    return BlastHsp(
        rank=as_int(raw.get("hsp_num")) or fallback_rank,
        score=as_int(raw.get("hsp_score")),
        bit_score=as_float(raw.get("hsp_bit_score")),
        expect=as_float(raw.get("hsp_expect")),
        align_length=as_int(raw.get("hsp_align_len")),
        identity_percent=as_float(raw.get("hsp_identity")),
        positive_percent=as_float(raw.get("hsp_positive")),
        gaps=as_int(raw.get("hsp_gaps")),
        query_start=as_int(raw.get("hsp_query_from")),
        query_end=as_int(raw.get("hsp_query_to")),
        hit_start=as_int(raw.get("hsp_hit_from")),
        hit_end=as_int(raw.get("hsp_hit_to")),
    )


def _uniprot_accession(accession: str) -> str | None:
    """The accession to import by, or None when the hit is not a UniProt entry.

    A nucleotide (blastn/tblastn) hit carries an EMBL/ENA identifier, which the
    import flow has no client for. Returning None there is what stops the UI
    offering an "Open" button that could only fail.
    """
    if not accession:
        return None
    try:
        return normalise_accession(accession)
    except SourceNotFoundError:
        return None


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# Module-level singleton, for the same reason `api/search.py` keeps its client
# singletons: the job store is supposed to survive between requests. Tests swap
# it through `set_registry` rather than reaching into private state.
_REGISTRY = BlastJobRegistry()


def get_registry() -> BlastJobRegistry:
    return _REGISTRY


def set_registry(registry: BlastJobRegistry) -> None:
    global _REGISTRY
    _REGISTRY = registry
