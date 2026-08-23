from __future__ import annotations

import logging
from pathlib import Path

from Bio.PDB import MMCIFParser, PDBParser
from Bio.PDB.Structure import Structure
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
from app.models.annotations import ProteinAnnotations
from app.models.protein import ProteinSummary
from app.services import analytics, annotations, ingest, registry
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.storage import local as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proteins", tags=["proteins"])

_STATIC = Path(__file__).parent.parent / "static"

# Parsed summaries live in `services/registry` so the import router (P5) can
# register into the same store this router reads from.


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
    if ext not in storage.ALLOWED_UPLOAD_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file extension. Allowed: pdb, cif, mmcif",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > storage.MAX_STRUCTURE_BYTES:
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
        summary = await ingest.parse_and_register(stored_path, uid, source="uploaded")
    except ingest.StructureParseFailed as exc:
        # Don't leak internal path from exc — use a generic message.
        raise HTTPException(
            status_code=400,
            detail="Failed to parse structure file. Check the file is a valid PDB or mmCIF.",
        ) from exc
    except ingest.EmptyStructureError as exc:
        # Parser returned empty structure (likely non-PDB content).
        raise HTTPException(
            status_code=400,
            detail="Could not parse any protein chains from the file. Check the file is a valid PDB or mmCIF structure.",
        ) from exc

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


def parse_structure_for_analytics(file_path: Path) -> Structure:
    """Parse a PDB or mmCIF file into a BioPython Structure for analytics use.

    Public because `api/compare.py` (P7) needs the same structure and the same
    analytics for two proteins at once; a second parse path would be a second
    place for the format detection to drift.
    """
    ext = file_path.suffix.lower().lstrip(".")
    if ext in ("cif", "mmcif"):
        bio_parser = MMCIFParser(QUIET=True)
    else:
        bio_parser = PDBParser(QUIET=True)
    return bio_parser.get_structure(file_path.stem, str(file_path))


def compute_analytics(
    uid: str, summary: ProteinSummary, file_path: Path
) -> AnalyticsResponse:
    """Orchestrate analytics service calls + assemble the response payload."""
    structure = parse_structure_for_analytics(file_path)

    # Aggregate composition / property distribution over all chains' sequences.
    full_seq = "".join(c.sequence for c in summary.chains)

    comp_entries = [CompositionEntry(**e) for e in analytics.composition(full_seq)]
    ss_result = analytics.secondary_structure(structure, path=file_path)
    ss = SecondaryStructurePercentages(
        helix=ss_result.helix,
        sheet=ss_result.sheet,
        coil=ss_result.coil,
        available=ss_result.available,
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


@router.get("/{uid}/annotations", response_model=ProteinAnnotations)
async def get_protein_annotations(uid: str) -> ProteinAnnotations:
    """Biological annotation for a stored protein, from UniProtKB (P6).

    A protein with no resolvable UniProt accession — the normal case for a
    plain upload — is not an error. It returns 200 with every section empty
    and `accession_resolved: false`, so the panel can say *why* it is empty
    instead of showing a failure the user cannot act on.

    502 is reserved for the one case where we know the accession and UniProt
    itself could not be reached: there, retrying is worth offering.
    """
    # Imported inside the handler: `api.search` owns the client singletons, and
    # importing it at module scope would make the two routers import-cyclic.
    from app.api.search import get_rcsb_client, get_uniprot_client

    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")

    uniprot = get_uniprot_client()
    accession, note = await annotations.resolve_accession(
        summary, uniprot=uniprot, rcsb=get_rcsb_client()
    )
    if accession is None:
        logger.info("No UniProt accession for %s: %s", uid, note)
        return annotations.empty_annotations(uid, note)

    try:
        entry = await uniprot.fetch_annotations(accession)
    except SourceNotFoundError as exc:
        logger.info("UniProt has no entry for %s (protein %s): %s", accession, uid, exc)
        return annotations.empty_annotations(
            uid, f"UniProt has no entry for accession {accession}.", accession=accession
        )
    except SourceUnavailableError as exc:
        logger.warning("UniProt annotations unavailable for %s: %s", accession, exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach UniProt for this protein's annotations. Try again.",
        ) from exc

    return annotations.build_annotations(uid, entry, accession=accession, note=note)


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
    return await run_in_threadpool(compute_analytics, uid, summary, file_path)
