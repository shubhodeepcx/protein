from __future__ import annotations

import logging
from pathlib import Path

from Bio.PDB import MMCIFParser, PDBParser
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.models.analytics import (
    AnalyticsResponse,
    ChainLength,
    CompositionEntry,
    HydrophobicityProfile,
    PropertyDistribution,
    SecondaryStructurePercentages,
)
from app.models.protein import ProteinSummary
from app.services import analytics, parser, registry
from app.storage import local as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proteins", tags=["proteins"])

_STATIC = Path(__file__).parent.parent / "static"

# Parsed summaries live in `services/registry` so the import router (P5) can
# register into the same store this router reads from.

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_ALLOWED_EXTS = {"pdb", "cif", "mmcif"}


@router.get("/demo/file")
def get_demo_file() -> FileResponse:
    pdb = _STATIC / "1CRN.pdb"
    if not pdb.exists():
        raise HTTPException(status_code=404, detail="Demo file not found")
    return FileResponse(str(pdb), media_type="chemical/x-pdb", filename="1CRN.pdb")


@router.post("/upload", response_model=ProteinSummary)
async def upload_protein(file: UploadFile = File(...)) -> ProteinSummary:
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file extension. Allowed: pdb, cif, mmcif",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // 1024} KB). Max 50 MB.",
        )

    try:
        uid, stored_path = storage.store_upload(content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Failed to write uploaded file to storage")
        raise HTTPException(
            status_code=500,
            detail="Failed to store uploaded file.",
        ) from exc

    try:
        summary = await run_in_threadpool(parser.parse, stored_path, uid=uid, source="uploaded")
    except Exception as exc:  # noqa: BLE001
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            pass
        # Don't leak internal path from exc — use a generic message.
        raise HTTPException(
            status_code=400,
            detail="Failed to parse structure file. Check the file is a valid PDB or mmCIF.",
        ) from exc

    if not summary.chains:
        # Parser returned empty structure (likely non-PDB content).
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(
            status_code=400,
            detail="Could not parse any protein chains from the file. Check the file is a valid PDB or mmCIF structure.",
        )

    registry.put(uid, summary)
    return summary


@router.get("/{uid}", response_model=ProteinSummary)
def get_protein(uid: str) -> ProteinSummary:
    # Validate format before cache lookup to avoid reflecting attacker input in 404 detail.
    try:
        storage.validate_uid(uid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Protein not found")
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")
    return summary


@router.get("/{uid}/file")
def get_protein_file(uid: str) -> FileResponse:
    try:
        path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    ext = path.suffix.lower().lstrip(".")
    media_type = "chemical/x-pdb" if ext == "pdb" else "chemical/x-mmcif"
    return FileResponse(str(path), media_type=media_type, filename=path.name)


def _parse_structure_for_analytics(file_path: Path):
    """Parse a PDB or mmCIF file into a BioPython Structure for analytics use."""
    ext = file_path.suffix.lower().lstrip(".")
    if ext in ("cif", "mmcif"):
        bio_parser = MMCIFParser(QUIET=True)
    else:
        bio_parser = PDBParser(QUIET=True)
    return bio_parser.get_structure(file_path.stem, str(file_path))


def _compute_analytics(
    uid: str, summary: ProteinSummary, file_path: Path
) -> AnalyticsResponse:
    """Orchestrate analytics service calls + assemble the response payload."""
    structure = _parse_structure_for_analytics(file_path)

    # Aggregate composition / property distribution over all chains' sequences.
    full_seq = "".join(c.sequence for c in summary.chains)

    comp_entries = [CompositionEntry(**e) for e in analytics.composition(full_seq)]
    ss = SecondaryStructurePercentages(
        **analytics.secondary_structure_percentages(structure, pdb_path=file_path)
    )
    prop = PropertyDistribution(**analytics.property_distribution(full_seq))

    # Hydrophobicity is computed on the LONGEST chain (the "primary" chain).
    primary = (
        max(summary.chains, key=lambda c: c.residue_count) if summary.chains else None
    )
    if primary is not None:
        hp_values = analytics.hydrophobicity_profile(primary.sequence, window=9)
        hp = HydrophobicityProfile(chain_id=primary.label, window=9, values=hp_values)
    else:
        hp = HydrophobicityProfile(chain_id="", window=9, values=[])

    chain_lengths = [
        ChainLength(chain_id=c.label, length=c.residue_count) for c in summary.chains
    ]

    return AnalyticsResponse(
        id=uid,
        molecular_weight=summary.molecular_weight,
        residue_count=summary.residue_count,
        atom_count=summary.atom_count,
        chain_count=len(summary.chains),
        composition=comp_entries,
        secondary_structure=ss,
        hydrophobicity=hp,
        property_distribution=prop,
        chain_lengths=chain_lengths,
    )


@router.get("/{uid}/analytics", response_model=AnalyticsResponse)
async def get_protein_analytics(uid: str) -> AnalyticsResponse:
    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")
    try:
        file_path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return await run_in_threadpool(_compute_analytics, uid, summary, file_path)
