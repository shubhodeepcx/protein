from __future__ import annotations

from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "proteins"


def store_upload(file_bytes: bytes, ext: str) -> tuple[str, Path]:
    raise NotImplementedError


def get_file(uid: str) -> Path:
    raise NotImplementedError
