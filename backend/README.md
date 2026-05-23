# ProteoLens Backend

FastAPI backend for the ProteoLens protein structure visualization platform.

## Prerequisites

- Python 3.11+

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Run Dev

```powershell
uvicorn app.main:app --reload --port 8000
```

## Tests

```powershell
pytest
```

## Env Vars

None in P0. Environment configuration is coming in later phases.

## Slice Design

See [../docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](../docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md).
