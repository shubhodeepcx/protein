"""Transport for EBI's NCBI BLAST REST service (P8).

**Pure transport.** One method per round trip, no waiting, no polling loop, no
job bookkeeping. Everything that decides *when* to make these calls lives in
`services/blast_jobs.py`, so `GET /api/blast/{job_id}` can answer a poll
without this module ever blocking a request.

Why EBI and not NCBI directly (slice design section 4): `blast.ncbi.nlm.nih.gov`
is rate-limited, discourages programmatic use and returns HTML-ish payloads.
EBI wraps the same NCBI binaries in a documented submit -> poll -> retrieve
contract that returns JSON.

The contract, verified against the live service on 2026-08-23:

| Operation        | Path                          | Method |
|------------------|-------------------------------|--------|
| Submit job       | `/run/`                       | POST (form-encoded) |
| Check status     | `/status/{jobId}`             | GET (bare status string) |
| Result types     | `/resulttypes/{jobId}`        | GET |
| Retrieve result  | `/result/{jobId}/{type}`      | GET |
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from app.models.blast import JOB_ID_RE, BlastProgram
from app.services.external import (
    ExternalSourceError,
    SourceNotFoundError,
    SourceUnavailableError,
    new_client,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast"

# EBI requires a contact address on every submission so they can reach the
# operator of a misbehaving client. Configure it per deployment with
# BLAST_CONTACT_EMAIL (see backend/.env.example).
#
# The default is a non-personal GitHub noreply address rather than any real
# person's mailbox. It is a *fallback*, not a recommendation: `submit` logs a
# warning whenever it is used, because a deployment that never sets a reachable
# address is one EBI is entitled to block.
CONTACT_EMAIL_ENV = "BLAST_CONTACT_EMAIL"
DEFAULT_CONTACT_EMAIL = "proteolens@users.noreply.github.com"

# Submitting and retrieving are ordinary short round trips — the *job* takes
# minutes, the HTTP calls do not — so the project-wide 10s timeout from
# `external.new_client()` applies unchanged.


class BlastRequestRejected(ExternalSourceError):
    """EBI refused the submission itself (bad program/database/sequence).

    Distinct from `SourceUnavailableError` because it is the caller's fault and
    retrying the same request will fail again: the router maps it to 400, not 502.
    """


def contact_email() -> str:
    """The address submitted to EBI, from the environment or the documented default."""
    configured = os.getenv(CONTACT_EMAIL_ENV, "").strip()
    return configured or DEFAULT_CONTACT_EMAIL


def validate_job_id(job_id: str) -> str:
    """Reject a job id that cannot be safely interpolated into a URL path."""
    candidate = job_id.strip()
    if not JOB_ID_RE.match(candidate):
        raise SourceNotFoundError(f"{job_id!r} is not a valid BLAST job id")
    return candidate


class EBIBlastClient:
    """Async client for `https://www.ebi.ac.uk/Tools/services/rest/ncbiblast`."""

    source = "ebi-ncbiblast"

    def __init__(self, base_url: str = BASE_URL, email: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._email = email

    @property
    def email(self) -> str:
        return self._email or contact_email()

    # ------------------------------------------------------------- submit

    async def submit(
        self,
        *,
        sequence: str,
        program: BlastProgram = "blastp",
        database: str = "uniprotkb",
        stype: str = "protein",
        exp: str | None = None,
        alignments: int | None = None,
        scores: int | None = None,
        matrix: str | None = None,
        filter_low_complexity: bool | None = None,
    ) -> str:
        """POST the search and return the job id. Does not wait for anything."""
        email = self.email
        if email == DEFAULT_CONTACT_EMAIL:
            logger.warning(
                "Submitting a BLAST job with the fallback contact address %s. "
                "Set %s to a reachable mailbox before deploying.",
                DEFAULT_CONTACT_EMAIL,
                CONTACT_EMAIL_ENV,
            )

        form: dict[str, str] = {
            "email": email,
            "program": program,
            "stype": stype,
            "database": database,
            "sequence": sequence,
        }
        if exp is not None:
            form["exp"] = exp
        if alignments is not None:
            form["alignments"] = str(alignments)
        if scores is not None:
            form["scores"] = str(scores)
        if matrix is not None:
            form["matrix"] = matrix
        if filter_low_complexity is not None:
            form["filter"] = "T" if filter_low_complexity else "F"

        async with new_client() as client:
            try:
                response = await client.post(f"{self._base_url}/run/", data=form)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"BLAST submission failed: {exc}") from exc

        if response.status_code == 400:
            # EBI puts the reason in the body; it is short and safe to surface.
            reason = response.text.strip()[:300] or "no reason given"
            raise BlastRequestRejected(f"EBI rejected the BLAST submission: {reason}")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"BLAST submission returned HTTP {response.status_code}"
            )

        job_id = response.text.strip()
        if not job_id or not JOB_ID_RE.match(job_id):
            raise SourceUnavailableError(
                "BLAST submission returned no usable job id"
            )
        logger.info("Submitted %s job %s against %s", program, job_id, database)
        return job_id

    # ------------------------------------------------------------- status

    async def status(self, job_id: str) -> str:
        """GET the job's current status. The body is a bare status string.

        Returns the raw upstream token — mapping it onto our `BlastStatus`
        vocabulary is policy, and policy lives in `blast_jobs`.
        """
        safe_id = validate_job_id(job_id)
        async with new_client() as client:
            try:
                response = await client.get(f"{self._base_url}/status/{safe_id}")
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"BLAST status request failed: {exc}") from exc

        if response.status_code == 404:
            # EBI expires jobs; a 404 here means the id is gone, not broken.
            return "NOT_FOUND"
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"BLAST status for {safe_id} returned HTTP {response.status_code}"
            )
        return response.text.strip().upper()

    # -------------------------------------------------------- result types

    async def result_types(self, job_id: str) -> list[str]:
        """The identifiers this finished job can be retrieved as."""
        safe_id = validate_job_id(job_id)
        async with new_client() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/resulttypes/{safe_id}",
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"BLAST result-types request failed: {exc}"
                ) from exc

        if response.status_code == 404:
            raise SourceNotFoundError(f"BLAST job {safe_id} has expired or never existed")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"BLAST result types for {safe_id} returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError(
                "BLAST result types returned a non-JSON body"
            ) from exc

        types = body.get("types") if isinstance(body, dict) else None
        if not isinstance(types, list):
            return []
        return [
            t["identifier"]
            for t in types
            if isinstance(t, dict) and isinstance(t.get("identifier"), str)
        ]

    # ----------------------------------------------------------- retrieve

    async def retrieve_json(self, job_id: str) -> dict[str, Any]:
        """GET the finished job's JSON result.

        The schema is published at github.com/ebi-jdispatcher/sss_json_schema;
        the recorded fixture the tests run against is a real response from it.
        """
        safe_id = validate_job_id(job_id)
        async with new_client() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/result/{safe_id}/json",
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(f"BLAST result request failed: {exc}") from exc

        if response.status_code == 404:
            raise SourceNotFoundError(f"BLAST job {safe_id} has expired or never existed")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"BLAST result for {safe_id} returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError("BLAST result returned a non-JSON body") from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError("BLAST result returned an unexpected payload")
        return body
