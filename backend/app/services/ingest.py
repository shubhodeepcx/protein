from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi.concurrency import run_in_threadpool

from app.models.protein import ProteinSummary
from app.services import parser, registry

logger = logging.getLogger(__name__)


class StructureParseError(Exception):
    """Base for `parse_and_register` failures. Callers catch the subclasses."""


class StructureParseFailed(StructureParseError):
    """The parser raised while reading the stored file."""


class EmptyStructureError(StructureParseError):
    """The file parsed but yielded no protein chains."""


class NucleicAcidOnlyError(EmptyStructureError):
    """The file holds DNA/RNA chains but no protein for them to be bound to.

    A subclass, so a caller that only knows `EmptyStructureError` still rejects
    it; callers that catch this first can say *why* instead of implying the
    file was unreadable.
    """


NUCLEIC_ACID_ONLY_DETAIL = (
    "The structure contains nucleic-acid chains ({chains}) but no protein chain. "
    "ProteoLens analyses proteins together with the DNA, RNA, ligands and ions "
    "bound to them, so a protein must be present."
)


async def parse_and_register(
    stored_path: Path,
    uid: str,
    *,
    source: Literal["uploaded", "rcsb", "alphafold", "uniprot"],
    source_id: str | None = None,
) -> ProteinSummary:
    """Parse an already-stored structure file and register it, or clean up and raise.

    Shared by the upload and import routers: both store a file first (each with
    its own error handling for *that* step), then need the identical
    parse -> validate -> register, unlink-on-any-failure behaviour this
    performs. Callers catch `StructureParseFailed` / `EmptyStructureError` and
    translate them into their own `HTTPException` (status code and message
    differ per route).
    """
    try:
        summary = await run_in_threadpool(
            parser.parse, stored_path, uid=uid, source=source, source_id=source_id
        )
    except Exception as exc:
        _unlink(stored_path)
        raise StructureParseFailed(str(exc)) from exc

    if not summary.chains:
        _unlink(stored_path)
        if summary.nucleic_acid_chains:
            raise NucleicAcidOnlyError(
                NUCLEIC_ACID_ONLY_DETAIL.format(chains=", ".join(summary.nucleic_acid_chains))
            )
        raise EmptyStructureError("Parsed structure has no protein chains")

    registry.put(uid, summary)
    return summary


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not clean up %s after a failed ingest", path.name)
