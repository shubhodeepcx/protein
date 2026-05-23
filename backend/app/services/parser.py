from __future__ import annotations

from pathlib import Path

from app.models.protein import ProteinSummary


async def parse(path: Path | str) -> ProteinSummary:
    raise NotImplementedError
