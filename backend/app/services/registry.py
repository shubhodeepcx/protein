from __future__ import annotations

from app.models.protein import ProteinSummary

# Single in-memory home for parsed protein summaries, shared by the upload path
# (`api/proteins.py`) and the import path (`api/import_.py`). Persistence is a
# later slice — this dict resets on restart.
#
# It lives in `services/` rather than inside a router so neither router has to
# reach into the other's private module state.
_SUMMARIES: dict[str, ProteinSummary] = {}


def put(uid: str, summary: ProteinSummary) -> None:
    """Register a parsed summary under its storage uid."""
    _SUMMARIES[uid] = summary


def get(uid: str) -> ProteinSummary | None:
    """Return the summary for `uid`, or None when it is not registered."""
    return _SUMMARIES.get(uid)


def clear() -> None:
    """Drop every registered summary. Used by tests."""
    _SUMMARIES.clear()


def size() -> int:
    """Number of currently registered summaries."""
    return len(_SUMMARIES)
