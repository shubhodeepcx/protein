from __future__ import annotations

import re
import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "proteins"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# The single 50 MB ceiling both the upload and import routers enforce, so a
# raised limit only needs to change here.
MAX_STRUCTURE_BYTES = 50 * 1024 * 1024

# Ordered so get_file returns pdb before cif when both exist (shouldn't happen, but safe).
# Extensions we actually persist to disk. Public: the upload router derives
# its client-facing allow-list from this plus _EXT_ALIASES below, rather than
# maintaining its own separate list that could drift from what store_upload
# accepts.
STORED_EXTS = ("pdb", "cif")

# Client-facing extension spellings that don't match a stored extension
# directly, mapped to the one we normalize them to.
_EXT_ALIASES: dict[str, str] = {"mmcif": "cif"}

# Every extension a client may legally name on upload or import: what we
# store, plus every alias that normalizes to something we store.
ALLOWED_UPLOAD_EXTS = frozenset(STORED_EXTS) | _EXT_ALIASES.keys()

_UID_RE = re.compile(r"^[0-9a-f]{32}$")


def validate_uid(uid: str) -> None:
    if not _UID_RE.match(uid):
        raise ValueError(f"Invalid uid: {uid!r}")


def _normalize_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return _EXT_ALIASES.get(ext, ext)


def store_upload(file_bytes: bytes, ext: str) -> tuple[str, Path]:
    ext = _normalize_ext(ext)
    if ext not in STORED_EXTS:
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
    for ext in STORED_EXTS:
        candidate = STORAGE_ROOT / f"{uid}.{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(uid)
