from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_json(name: str) -> Any:
    """Load a recorded external API response from tests/fixtures/."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def load_bytes(name: str) -> bytes:
    """Load a recorded structure file from tests/fixtures/."""
    return (FIXTURES / name).read_bytes()


def pdb_1crn_bytes() -> bytes:
    """The bundled 1CRN PDB, used as a stand-in for a downloaded structure."""
    static = Path(__file__).resolve().parents[1] / "app" / "static" / "1CRN.pdb"
    return static.read_bytes()
