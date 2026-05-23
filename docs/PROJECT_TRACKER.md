# Project Tracker

**Project:** AI-Powered Protein Structure Visualization Platform
**Living document.** Read before claiming work. Update on claim, on PR open, on merge.

**Last updated:** 2026-05-23 by Shubhodeep Chatterjee (P0 scaffold committed at 61c1355)

---

## Current phase

**P0 — Scaffold**

Active design: [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](superpowers/specs/2026-05-23-protein-mvp-slice-design.md)

---

## In progress

_All P0 build tasks done. P0 integration smoke test is the only thing keeping the phase from being fully Done — it requires running `pip install` in the backend venv and starting both servers, which needs user authorization._

| Task | Owner | Branch | Status | Notes |
|---|---|---|---|---|

---

## Ready to claim

Tasks with no unresolved dependencies. Pick one, move it to In progress, then start work.

| Task | Phase | Dependencies | Estimate |
|---|---|---|---|
| P0 integration smoke test (`docs/smoke-tests.md` → P0 section) | P0 | backend pip install, both servers running | 10m once installed |
| P1: bundle 1CRN PDB in `backend/app/static/` and serve via `GET /api/proteins/demo/file` | P1 | P0 smoke pass | 20m |
| P1: `MolstarViewer.tsx` component (Mol* wrapper with imperative ref API) | P1 | P0 smoke pass | 2h |
| P1: `/viewer/demo` page using the wrapper | P1 | MolstarViewer + demo file route | 30m |
| P1: smoke test for P1 in `docs/smoke-tests.md` | P1 | P1 features | 15m |

---

## Blocked

_No blocked tasks._

| Task | Blocked by | Notes |
|---|---|---|

---

## Done

| Task | Phase | Date | PR / commit |
|---|---|---|---|
| Source docs imported (spec.md, sdlc.md, project_report.md) | pre-P0 | 2026-05-23 | initial extract |
| MVP slice design | pre-P0 | 2026-05-23 | `0678ae8` |
| AGENTS.md created | pre-P0 | 2026-05-23 | `0678ae8` |
| PROJECT_TRACKER.md created | pre-P0 | 2026-05-23 | `0678ae8` |
| Repo `.gitignore` (root) | P0 | 2026-05-23 | `0678ae8`, refined in `61c1355` |
| Repo root `README.md` | P0 | 2026-05-23 | `61c1355` |
| `docs/smoke-tests.md` skeleton with P0 verification script | P0 | 2026-05-23 | `61c1355` |
| Next.js scaffold (Next 16 + TS strict + Tailwind v4 + shadcn + Zustand v5, 3-col layout shell, HealthPill, lib/api, store slices, Vitest with 7/7 tests) | P0 | 2026-05-23 | `61c1355` |
| FastAPI scaffold (FastAPI 0.110+ + Python 3.11+ + pyproject, CORS, /health, Pydantic ProteinSummary, stub modules for parser/analytics/rcsb/alphafold/uniprot/storage, pytest test_health passing) | P0 | 2026-05-23 | `61c1355` (Codex subagent) |

---

## Decisions log

Append-only. Never edit past entries — supersede with a new entry referencing the old one.

| Date | Decision | Rationale | Reversible? |
|---|---|---|---|
| 2026-05-23 | Build MVP slice end-to-end (Approach A vertical-slice) | Tighter feedback loop than frontend-first or backend-first; demoable at every phase | yes |
| 2026-05-23 | Next.js + FastAPI split per spec | Python needed for BioPython now and DSSP / Foldseek later | hard — affects all of backend |
| 2026-05-23 | Skip auth + DB this slice | Faster to working viewer + analytics; avoid weeks of migration plumbing | yes (separate slice when ready) |
| 2026-05-23 | Monorepo at `g:\protein` | Solo dev; keeps frontend + backend in sync | yes |
| 2026-05-23 | Local commands, no Docker | Fastest dev loop; add Docker when services compose grows beyond two | yes |
| 2026-05-23 | Zustand for frontend state | Smaller than Redux; clean fit with Mol* imperative API | yes |
| 2026-05-23 | Local disk UUID-keyed file storage | Trivial; defer MinIO/S3 until deployment | yes |
| 2026-05-23 | Read secondary structure from PDB HELIX/SHEET headers; defer DSSP | Avoid native binary dependency in P0–P3 | yes — DSSP slice later |
| 2026-05-23 | Recharts for charts (not Plotly/ECharts) | Smaller bundle, more idiomatic React | yes |
| 2026-05-23 | Next.js 16 (not 14) | Latest stable when scaffolded; App Router unchanged; Next 16 removed `next lint` so `lint` script runs `tsc --noEmit` | yes |
| 2026-05-23 | shadcn CLI defaults (style `base-nova`, base color `neutral`) | Current shadcn CLI no longer exposes "New York" / "Slate" flags from spec; `neutral` is essentially slate without the blue tint | yes |
| 2026-05-23 | Zustand v5 (not v4) | npm latest; slice composition pattern unchanged | yes |
| 2026-05-23 | Tailwind v4 (default from create-next-app) | Modern PostCSS-based; CSS variables on; works cleanly with shadcn | yes |
| 2026-05-23 | next-themes for theme provider; dark mode default | Canonical shadcn integration; sci tool reads better dark | yes |

---

## Phase backlog

### P0 — Scaffold

Goal: both servers run, frontend → backend smoke test passes.

- [x] Repo root README + .gitignore
- [x] Next.js init in `frontend/` (App Router, TS strict, Tailwind, shadcn/ui base)
- [x] FastAPI init in `backend/` (pyproject.toml with httpx + biopython + pydantic + fastapi + uvicorn, `app/main.py` with CORS, `/health` endpoint)
- [x] Frontend `lib/api.ts` calls `/health` and renders status on landing page
- [x] `docs/smoke-tests.md` with the P0 smoke test recorded
- [ ] **Integration smoke test:** start both servers, confirm green pill on landing page. Requires `pip install -e ".[dev]"` in backend venv (pending user authorization).

### P1 — Static viewer

Goal: open `/viewer/demo` and rotate a real 3D crambin.

- [ ] Bundle 1CRN PDB in `backend/app/static/`
- [ ] `GET /api/proteins/demo/file` serves the bundled file
- [ ] `MolstarViewer.tsx` component with `loadStructure`, `setRepresentation`, `setColoring`, `resetCamera` imperative API
- [ ] `/viewer/demo` page using the wrapper
- [ ] P1 smoke test in `docs/smoke-tests.md`

### P2 — Upload + parse

Goal: drag a PDB onto the home page → see it render.

- [ ] `DropZone.tsx` with client-side validation (extension, size)
- [ ] `services/parser.py` (BioPython, returns `ProteinSummary`)
- [ ] `services/storage/local.py` (UUID-keyed)
- [ ] `models/protein.py` (Pydantic ProteinSummary, ChainInfo)
- [ ] `POST /api/proteins/upload`
- [ ] `GET /api/proteins/{id}` (returns ProteinSummary)
- [ ] `GET /api/proteins/{id}/file` (binary)
- [ ] Frontend `/viewer/[id]` page loads from API
- [ ] Backend pytest: 1CRN parser test
- [ ] P2 smoke test

### P3 — Dashboard

Goal: upload → analytics appear beside viewer.

- [ ] `services/analytics.py` (MW, composition, hydrophobicity, SS%, property distribution)
- [ ] `GET /api/proteins/{id}/analytics`
- [ ] Metric cards (MW, residues, atoms, chains)
- [ ] Composition bar chart (Recharts)
- [ ] SS donut chart
- [ ] Hydrophobicity line chart (Kyte-Doolittle, window 9)
- [ ] Chain length bar chart
- [ ] Backend pytest: MW + composition for crambin
- [ ] P3 smoke test

### P4 — Sequence panel

Goal: bidirectional click sync between sequence and 3D.

- [ ] `SequencePanel.tsx` (per-chain, color by residue type)
- [ ] Zustand `selectionSlice`
- [ ] Mol* selection event → store dispatch
- [ ] Store subscribe → Mol* `highlightResidues`
- [ ] Residue search input (`A:123` syntax)
- [ ] Frontend Vitest: selection reducer tests
- [ ] P4 smoke test

### P5 — DB search + import

Goal: search "insulin", click a result, see it in the viewer.

- [ ] `services/rcsb.py` (search, fetch_metadata, download_structure)
- [ ] `services/alphafold.py` (search via UniProt cross-ref, fetch model)
- [ ] `services/uniprot.py` (search, fetch_metadata)
- [ ] `GET /api/search?q=&source=` with `asyncio.gather` fan-out + dedupe
- [ ] `POST /api/proteins/import`
- [ ] `app/search/page.tsx` (search input, result cards, source filter)
- [ ] Backend pytest: each client with recorded HTTP fixtures (respx / pytest-httpx)
- [ ] P5 smoke test

---

## Out of scope for this slice

Tracked here so future agents don't accidentally pull them in:

- AI annotation assistant (F8) — separate slice
- Mutation impact visualizer (A2) — separate slice
- Comparative protein view (A3) — separate slice
- Similarity search (A4) — separate slice
- Contact map (A6) — separate slice
- Export system (F9: PDF / PNG / JSON / CSV) — separate slice
- User accounts + Postgres + projects — separate slice
- DSSP integration — separate slice (when we go beyond P3)
- Docker / CI / deployment — separate slice
- Stretch features S1–S4 (MD viewer, energy minimization, docking, async folding) — post-MVP
