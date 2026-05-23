from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.models.protein import ProteinSummary
from app.services import parser
from app.storage import local as storage

router = APIRouter(prefix="/proteins", tags=["proteins"])

_STATIC = Path(__file__).parent.parent / "static"

# In-memory cache: uid -> ProteinSummary. Resets on server restart; persistence
# is a later slice.
_SUMMARY_CACHE: dict[str, ProteinSummary] = {}

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTS = {"pdb", "cif", "mmcif"}


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
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Max {MAX_UPLOAD_BYTES} bytes.",
        )

    try:
        uid, stored_path = storage.store_upload(content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        summary = await parser.parse(stored_path, uid=uid, source="uploaded")
    except Exception as exc:  # noqa: BLE001
        # Clean up the stored file if parsing fails so we don't leak disk space.
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse structure: {exc}",
        ) from exc

    _SUMMARY_CACHE[uid] = summary
    return summary


@router.get("/{uid}", response_model=ProteinSummary)
def get_protein(uid: str) -> ProteinSummary:
    summary = _SUMMARY_CACHE.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Protein {uid} not found")
    return summary


@router.get("/{uid}/file")
def get_protein_file(uid: str) -> FileResponse:
    try:
        path = storage.get_file(uid)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"File for {uid} not found",
        ) from exc

    ext = path.suffix.lower().lstrip(".")
    media_type = "chemical/x-pdb" if ext == "pdb" else "chemical/x-mmcif"
    return FileResponse(str(path), media_type=media_type, filename=path.name)
