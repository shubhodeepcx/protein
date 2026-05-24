from __future__ import annotations

import re
import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "proteins"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# Ordered so get_file returns pdb before cif when both exist (shouldn't happen, but safe).
_ALLOWED_EXTS = ("pdb", "cif")
_UID_RE = re.compile(r"^[0-9a-f]{32}$")


def validate_uid(uid: str) -> None:
    if not _UID_RE.match(uid):
        raise ValueError(f"Invalid uid: {uid!r}")


def store_upload(file_bytes: bytes, ext: str) -> tuple[str, Path]:
    ext = ext.lower().lstrip(".")
    if ext == "mmcif":
        ext = "cif"
    if ext not in _ALLOWED_EXTS:
        raise ValueError(f"Unsupported extension: {ext!r}")
    uid = uuid.uuid4().hex
    path = STORAGE_ROOT / f"{uid}.{ext}"
    try:
        path.write_bytes(file_bytes)
    except OSError as exc:
        raise OSError(f"Could not write upload to storage: {exc}") from exc
    return uid, path


def get_file(uid: str) -> Path:
    validate_uid(uid)
    for ext in _ALLOWED_EXTS:
        candidate = STORAGE_ROOT / f"{uid}.{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(uid)
