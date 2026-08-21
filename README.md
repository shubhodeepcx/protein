# ProteoLens — AI-Powered Protein Structure Visualization Platform

A web-based workspace for protein 3D visualization, structural analysis, annotation, and reporting. Combines a Mol*-based molecular viewer with bioinformatics pipelines, public-database integration (RCSB PDB, AlphaFold DB, UniProt), and AI-assisted annotation.

**Status:** MVP slice P0–P5 complete and verified. Viewer, upload + parse, analytics dashboard, sequence panel with bidirectional 3D selection sync, and public-database search + import (RCSB PDB, AlphaFold DB, UniProt). 123 backend + 119 frontend tests green, and the manual smoke tests have been executed in a real browser against the live public APIs — see [docs/smoke-tests.md](docs/smoke-tests.md). Follow-ups are tracked in [docs/PROJECT_TRACKER.md](docs/PROJECT_TRACKER.md).

**Smoke tests:** After setup, run [docs/smoke-tests.md](docs/smoke-tests.md) to verify each phase end-to-end.

---

## Project layout

```
.
├── frontend/   # Next.js 16 (App Router, TypeScript), Tailwind v4, shadcn/ui, Zustand, Mol* 5
├── backend/    # FastAPI 0.110+, Python 3.11+, BioPython, httpx
├── docs/
│   ├── spec.md                                  # Full 6-month product + technical spec
│   ├── sdlc.md                                  # 6-month phase plan
│   ├── project_report.md                        # Project report (background, motivation, scope)
│   ├── PROJECT_TRACKER.md                       # Living tracker — claim-before-code
│   ├── smoke-tests.md                           # Per-phase manual verification scripts
│   └── superpowers/specs/                       # Slice designs
└── AGENTS.md   # Rules for AI contributors (Codex, etc.)
```

The full 6-month roadmap is in [docs/spec.md](docs/spec.md). The **active slice** (P0–P5: viewer + upload + parse + dashboard + sequence panel + DB import; no auth, no DB, no AI) is in [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md).

---

## Quick start

**Double-click `start.cmd`** (or run it from a terminal).

That is the whole thing. It installs anything missing, builds the frontend, starts both
services, and opens the app in your browser. Press <kbd>Ctrl</kbd>+<kbd>C</kbd> to stop both.

```powershell
.\start.cmd              # run it
.\start.cmd -Rebuild     # force a fresh frontend build after changing source
.\start.cmd -NoBrowser   # start the servers without opening a browser
```

The first run takes a few minutes (virtualenv + npm install + production build). Every run
after that starts in seconds.

The launcher serves a **production build** rather than the dev server. That is deliberate:
`next dev` paints a floating dev-tools bubble over every page, and `next start` does not.
For active development with hot reload, use the two-terminal flow under [Run](#run) below.

---

## Prerequisites

- **Node.js** 20+ and **npm** 10+
- **Python** 3.11+
- A modern browser (Chrome/Edge/Firefox) for the Mol* viewer

No Docker required at this stage; both services run from your shell.

---

## Setup

Only needed if you are not using `start.cmd`, which does all of this for you.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # PowerShell
# or: source .venv/bin/activate   # bash
pip install -e ".[dev]"
```

### Frontend

```powershell
cd frontend
npm install
```

---

## Run

Two terminals — one for each service.

**Terminal 1 — backend** (`http://localhost:8000`):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- Swagger UI at `http://localhost:8000/docs`
- Health check at `http://localhost:8000/health`

**Terminal 2 — frontend** (`http://localhost:3000`):

```powershell
cd frontend
npm run dev
```

The landing page shows a "Backend OK" / "Backend unreachable" pill so you can confirm wiring at a glance.

---

## Testing

```powershell
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

---

## Working on the project

If you're contributing — human or AI agent — read [AGENTS.md](AGENTS.md) first. It covers:

- Mandatory reading order
- Claim-before-code via [docs/PROJECT_TRACKER.md](docs/PROJECT_TRACKER.md)
- Branch / commit conventions (`feature/<phase>-<slug>`, co-author footers)
- Coding standards (TS strict on frontend, full type hints on backend)
- Definition of done (smoke test passes, tracker updated, decisions logged)
- Parallel-work etiquette and destructive-action gate

The **active slice design** lives at [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md). It defines P0–P5 and lists what's intentionally out of scope.

---

## Documentation index

- [Spec](docs/spec.md)
- [SDLC plan](docs/sdlc.md)
- [Project report](docs/project_report.md)
- [Active slice design](docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md)
- [Project tracker](docs/PROJECT_TRACKER.md)
- [Smoke tests](docs/smoke-tests.md)
- [AGENTS.md](AGENTS.md)
