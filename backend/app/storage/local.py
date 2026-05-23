from __future__ import annotations

import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "proteins"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {"pdb", "cif", "mmcif"}


def store_upload(file_bytes: bytes, ext: str) -> tuple[str, Path]:
    """Save bytes to STORAGE_ROOT under a fresh UUID, return (uid, path)."""
    ext = ext.lower().lstrip(".")
    if ext == "mmcif":
        ext = "cif"
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported extension: {ext}")
    uid = uuid.uuid4().hex
    path = STORAGE_ROOT / f"{uid}.{ext}"
    path.write_bytes(file_bytes)
    return uid, path


def get_file(uid: str) -> Path:
    """Find the stored file for this uid across allowed extensions.

    Raises FileNotFoundError when no candidate exists.
    """
    for ext in ALLOWED_EXTS:
        candidate = STORAGE_ROOT / f"{uid}.{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(uid)
