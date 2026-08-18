from __future__ import annotations

import logging
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.api.search import get_client
from app.models.protein import ProteinSummary
from app.models.search import ImportRequest, SourceName
from app.services import parser, registry
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.storage import local as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proteins/import", tags=["import"])

# Same ceiling the upload path enforces — an external source should not be able
# to hand us something we would have rejected from a browser.
MAX_IMPORT_BYTES = 50 * 1024 * 1024

# UniProt hosts no coordinates of its own: importing from UniProt downloads the
# entry's AlphaFold model, so the stored summary is an AlphaFold structure.
# (`ProteinSummary.source` is Literal["uploaded", "rcsb", "alphafold"].)
_PARSER_SOURCE: dict[SourceName, Literal["rcsb", "alphafold"]] = {
    "rcsb": "rcsb",
    "alphafold": "alphafold",
    "uniprot": "alphafold",
}

_NOT_FOUND_MESSAGE: dict[SourceName, str] = {
    "rcsb": "RCSB PDB has no entry {id}.",
    "alphafold": "AlphaFold DB has no model for accession {id}.",
    "uniprot": "UniProt entry {id} has no AlphaFold model to import.",
}

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def _echo_id(source_id: str) -> str:
    """Render an identifier for an error message, without echoing junk back."""
    return f"'{source_id}'" if _SAFE_ID_RE.match(source_id) else "the requested identifier"


@router.post("", response_model=ProteinSummary)
async def import_protein(payload: ImportRequest) -> ProteinSummary:
    """Import a structure from an external database into local storage.

    Mirrors the upload path end to end (spec 6.2): download -> store -> parse ->
    register -> return the same `ProteinSummary` the upload endpoint returns, so
    `/viewer/{id}` works with no frontend changes.
    """
    source = payload.source
    source_id = payload.source_id.strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="'source_id' must not be empty.")

    client = get_client(source)

    try:
        content, ext = await client.download_structure(source_id)
    except SourceNotFoundError as exc:
        logger.info("Import 404 for %s:%s — %s", source, source_id, exc)
        raise HTTPException(
            status_code=404,
            detail=_NOT_FOUND_MESSAGE[source].format(id=_echo_id(source_id)),
        ) from exc
    except SourceUnavailableError as exc:
        logger.warning("Import upstream failure for %s:%s — %s", source, source_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach {source.upper()} to download this structure. Try again.",
        ) from exc

    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Structure is too large ({len(content) // 1024} KB). Max 50 MB.",
        )

    try:
        uid, stored_path = storage.store_upload(content, ext)
    except (ValueError, OSError) as exc:
        logger.error("Import storage failure for %s:%s — %s", source, source_id, exc)
        raise HTTPException(
            status_code=500, detail="Could not store the downloaded structure."
        ) from exc

    def _unlink() -> None:
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not clean up %s after a failed import", stored_path.name)

    try:
        summary = await run_in_threadpool(
            parser.parse,
            stored_path,
            uid=uid,
            source=_PARSER_SOURCE[source],
            source_id=source_id,
        )
    except Exception as exc:
        _unlink()
        logger.warning("Import parse failure for %s:%s — %r", source, source_id, exc)
        # Generic message: never leak the stored path or the raw exception text.
        raise HTTPException(
            status_code=400,
            detail="Failed to parse the downloaded structure file.",
        ) from exc

    if not summary.chains:
        _unlink()
        raise HTTPException(
            status_code=400,
            detail="The downloaded structure contained no protein chains.",
        )

    registry.put(uid, summary)
    logger.info("Imported %s:%s as %s", source, source_id, uid)
    return summary
