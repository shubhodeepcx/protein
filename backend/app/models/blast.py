"""API models for the P8 BLAST flow.

BLAST is the project's first genuinely asynchronous feature: a search takes
30 s to several minutes, so the request/response shape everywhere else in this
codebase does not fit. The models are therefore split across the two calls that
make it asynchronous:

* `BlastSubmitRequest` / `BlastSubmitResponse` — the submit round trip. The
  response carries a job id and the echo of what was submitted, and nothing
  else; there are no results yet and pretending otherwise would be a lie.
* `BlastJobStatus` — the poll round trip. It always carries a status, and a
  `result` only once the status is `FINISHED`.

Everything optional defaults to None / empty so a partial upstream payload
still validates: BLAST result JSON varies by program, and a missing field is
"not reported for this program", not a broken response.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# The four programs the slice design (section 4) marked achievable through
# EBI's REST service. smartBLAST and hosted IgBLAST have no public API and are
# deliberately absent rather than silently mapped onto something else.
BlastProgram = Literal["blastp", "blastn", "tblastn", "blastx"]

# Which kind of sequence each program takes as its *query*. EBI's `stype`
# parameter describes the query, not the database, so tblastn (protein query
# against a translated nucleotide database) is "protein".
PROGRAM_QUERY_TYPE: dict[str, Literal["protein", "dna"]] = {
    "blastp": "protein",
    "tblastn": "protein",
    "blastn": "dna",
    "blastx": "dna",
}

# EBI's documented job states, plus NOT_FOUND for an expired/unknown job id.
BlastStatus = Literal["QUEUED", "RUNNING", "FINISHED", "FAILURE", "ERROR", "NOT_FOUND"]

# A status the job will never leave. `blast_jobs` answers a poll on one of
# these from memory, with no upstream round trip at all.
TERMINAL_STATUSES: frozenset[str] = frozenset({"FINISHED", "FAILURE", "ERROR", "NOT_FOUND"})

# Rejection bound on the query, not a truncation. Titin — the longest known
# protein — is ~35,000 residues, and EBI rejects queries far below this, so a
# submission above it is a bug or an abuse, never a real protein. It scales
# with nothing: it is an absolute biological ceiling with an order of
# magnitude of headroom, and a query over it is refused with an error rather
# than quietly cut down to size.
MAX_QUERY_RESIDUES = 100_000

# Sequence letters we forward untouched: the 20 standard amino acids, the
# ambiguity codes (B/J/Z/X), nucleotides, gaps, and stop codons. Anything else
# is rejected here rather than sent upstream for EBI to reject slowly.
_SEQUENCE_CHARS = re.compile(r"^[A-Za-z*\-]+$")

# EBI database names are lowercase identifiers ("uniprotkb",
# "uniprotkb_swissprot", "em_rel"). Constraining the shape keeps an arbitrary
# string out of the form body we POST.
_DATABASE_RE = re.compile(r"^[a-z0-9_]{1,64}$")

# Substitution matrices EBI publishes for the protein programs.
_MATRIX_RE = re.compile(r"^[A-Za-z0-9]{2,20}$")

# EBI job ids look like `ncbiblast-R20191128-094014-0332-71107816-p1m`. This is
# interpolated straight into a URL path, so it is validated before use — an
# unconstrained job id is a path-traversal / SSRF hole.
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def normalise_sequence(raw: str) -> str:
    """Strip FASTA headers and whitespace, upper-case, and validate the residues.

    Raises `ValueError` with a message meant for the user. Never truncates: a
    query too long to run is refused, because silently BLASTing a prefix of the
    protein and labelling the answer with the protein's name would be wrong.
    """
    lines = [line for line in raw.splitlines() if not line.lstrip().startswith(">")]
    sequence = "".join(lines).replace(" ", "").replace("\t", "").upper()
    if not sequence:
        raise ValueError("Sequence is empty after removing FASTA headers and whitespace.")
    if not _SEQUENCE_CHARS.match(sequence):
        raise ValueError(
            "Sequence contains characters that are not amino-acid or nucleotide letters."
        )
    if len(sequence) > MAX_QUERY_RESIDUES:
        raise ValueError(
            f"Sequence is {len(sequence)} residues; the maximum accepted is "
            f"{MAX_QUERY_RESIDUES}."
        )
    return sequence


class BlastSubmitRequest(BaseModel):
    """`POST /api/blast`.

    Exactly one of `protein_id` (a locally stored structure, whose sequence we
    already hold) or `sequence` (a pasted query) must be given. blastp is the
    default because the protein sequence is the thing this application always
    has to hand.
    """

    protein_id: str | None = Field(
        None, description="Local protein uid; its sequence is used as the query."
    )
    chain_id: str | None = Field(
        None,
        description="Chain label to take the query from. Defaults to the longest chain.",
    )
    sequence: str | None = Field(
        None, description="Raw query sequence, as an alternative to protein_id."
    )
    program: BlastProgram = Field("blastp", description="BLAST program to run.")
    database: str = Field("uniprotkb", description="EBI database name to search.")
    exp: str = Field("1e-3", description="E-value threshold, e.g. '1e-3' or '10'.")
    alignments: int = Field(50, ge=1, le=1000, description="Maximum alignments to return.")
    scores: int = Field(50, ge=1, le=1000, description="Maximum scores to return.")
    matrix: str | None = Field(None, description="Substitution matrix, e.g. BLOSUM62.")
    filter_low_complexity: bool = Field(
        False, description="Mask low-complexity regions of the query."
    )

    @field_validator("database")
    @classmethod
    def _check_database(cls, value: str) -> str:
        name = value.strip().lower()
        if not _DATABASE_RE.match(name):
            raise ValueError(
                "Database must be an EBI database name such as 'uniprotkb'."
            )
        return name

    @field_validator("matrix")
    @classmethod
    def _check_matrix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip().upper()
        if not _MATRIX_RE.match(name):
            raise ValueError("Matrix must be a name such as 'BLOSUM62' or 'PAM70'.")
        return name

    @field_validator("exp")
    @classmethod
    def _check_exp(cls, value: str) -> str:
        text = value.strip()
        try:
            threshold = float(text)
        except ValueError as exc:
            raise ValueError("E-value threshold must be a number, e.g. '1e-3'.") from exc
        if threshold <= 0:
            raise ValueError("E-value threshold must be greater than zero.")
        return text

    @model_validator(mode="after")
    def _exactly_one_query_source(self) -> BlastSubmitRequest:
        has_id = bool((self.protein_id or "").strip())
        has_seq = bool((self.sequence or "").strip())
        if has_id == has_seq:
            raise ValueError("Provide exactly one of 'protein_id' or 'sequence'.")
        if has_id and self.sequence is not None:
            # Keep the two mutually exclusive on the model too, so a downstream
            # reader can never pick the wrong one.
            object.__setattr__(self, "sequence", None)
        return self

    @property
    def query_type(self) -> Literal["protein", "dna"]:
        """The `stype` EBI expects for this program's query."""
        return PROGRAM_QUERY_TYPE[self.program]


class BlastSubmitResponse(BaseModel):
    """The submit round trip. A job id and the echo of what was submitted.

    Carries no results by design — at this point the search has not started.
    """

    job_id: str = Field(..., description="EBI job identifier; poll with this.")
    status: BlastStatus = Field(..., description="Status at submission time.")
    program: BlastProgram = Field(..., description="Program that was submitted.")
    database: str = Field(..., description="Database being searched.")
    query_length: int = Field(..., description="Length of the submitted query sequence.")
    query_source: str = Field(
        ..., description="Where the query came from, for display in the UI."
    )
    submitted_at: datetime = Field(..., description="UTC submission timestamp.")
    poll_url: str = Field(..., description="Relative URL to poll for status and results.")


class BlastHsp(BaseModel):
    """One high-scoring segment pair within a hit.

    The aligned sequence strings (`hsp_qseq` / `hsp_mseq` / `hsp_hseq`) are
    deliberately not carried: they are ~90% of the payload by size and the
    results table does not render them. Coordinates are kept so the UI can show
    which part of the query a hit covers.
    """

    rank: int = Field(..., description="1-based HSP number within the hit.")
    score: int | None = Field(None, description="Raw alignment score.")
    bit_score: float | None = Field(None, description="Normalised bit score.")
    expect: float | None = Field(None, description="E-value for this HSP.")
    align_length: int | None = Field(None, description="Length of the alignment.")
    identity_percent: float | None = Field(None, description="Percent identical residues.")
    positive_percent: float | None = Field(None, description="Percent positive-scoring.")
    gaps: int | None = Field(None, description="Number of gap positions.")
    query_start: int | None = Field(None, description="1-based query start.")
    query_end: int | None = Field(None, description="1-based query end.")
    hit_start: int | None = Field(None, description="1-based subject start.")
    hit_end: int | None = Field(None, description="1-based subject end.")


class BlastHit(BaseModel):
    """One database match.

    The top-level `identity_percent` / `expect` / `score` are the *best* HSP's,
    chosen by score rather than by taking `hit_hsps[0]` — EBI happens to order
    them by score today, and a table that silently reports a weaker alignment
    if that ever changed would be very hard to notice.
    """

    rank: int = Field(..., description="1-based hit number, as ranked by BLAST.")
    accession: str = Field(..., description="Subject accession, e.g. P35858.")
    entry_id: str | None = Field(None, description="Subject entry name, e.g. ALS_HUMAN.")
    description: str | None = Field(None, description="Subject description line.")
    database: str | None = Field(None, description="Subject database code, e.g. SP.")
    organism: str | None = Field(None, description="Subject source organism.")
    gene: str | None = Field(None, description="Subject gene name when reported.")
    length: int | None = Field(None, description="Subject sequence length.")
    url: str | None = Field(None, description="Outbound link EBI resolved for the hit.")
    uniprot_accession: str | None = Field(
        None,
        description="Accession to import by, when the hit is a UniProt entry. "
        "None means this hit cannot be opened in the viewer.",
    )
    identity_percent: float | None = Field(None, description="Best HSP's percent identity.")
    expect: float | None = Field(None, description="Best HSP's E-value.")
    score: int | None = Field(None, description="Best HSP's raw score.")
    bit_score: float | None = Field(None, description="Best HSP's bit score.")
    align_length: int | None = Field(None, description="Best HSP's alignment length.")
    gaps: int | None = Field(None, description="Best HSP's gap count.")
    hsps: list[BlastHsp] = Field(default_factory=list, description="Every HSP for this hit.")


class BlastResult(BaseModel):
    """The parsed contents of a finished job's JSON result."""

    program: str | None = Field(None, description="Program the service actually ran.")
    version: str | None = Field(None, description="BLAST version string.")
    databases: list[str] = Field(default_factory=list, description="Databases searched.")
    query_id: str | None = Field(None, description="Query identifier EBI assigned.")
    query_definition: str | None = Field(None, description="Query definition line.")
    query_length: int | None = Field(None, description="Query length in residues/bases.")
    hit_count: int = Field(0, description="Number of hits returned.")
    hits: list[BlastHit] = Field(default_factory=list)
    started_at: str | None = Field(None, description="Service-reported start timestamp.")
    finished_at: str | None = Field(None, description="Service-reported end timestamp.")


class BlastJobStatus(BaseModel):
    """`GET /api/blast/{job_id}` — the poll round trip.

    `result` is populated only once `status` is FINISHED. `elapsed_seconds` and
    `poll_count` exist so the UI can show real progress — how long the job has
    actually been running — rather than a spinner that looks hung.
    """

    job_id: str = Field(..., description="EBI job identifier.")
    status: BlastStatus = Field(..., description="Current job status.")
    finished: bool = Field(..., description="True once the job will not change again.")
    program: BlastProgram = Field(..., description="Program that was submitted.")
    database: str = Field(..., description="Database being searched.")
    query_length: int = Field(..., description="Length of the submitted query sequence.")
    query_source: str = Field(..., description="Where the query came from.")
    submitted_at: datetime = Field(..., description="UTC submission timestamp.")
    elapsed_seconds: float = Field(..., description="Seconds since submission.")
    poll_count: int = Field(..., description="Upstream status checks made for this job.")
    message: str = Field(..., description="Human-readable explanation of the status.")
    result: BlastResult | None = Field(
        None, description="Parsed results; present only when status is FINISHED."
    )
