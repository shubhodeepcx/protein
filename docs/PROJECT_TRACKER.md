# Project Tracker

**Project:** AI-Powered Protein Structure Visualization Platform
**Living document.** Read before claiming work. Update on claim, on PR open, on merge.

**Last updated:** 2026-05-23 by Shubhodeep Chatterjee (initial seed from MVP slice design)

---

## Current phase

**P0 — Scaffold**

Active design: [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](superpowers/specs/2026-05-23-protein-mvp-slice-design.md)

---

## In progress

| Task | Owner | Branch | Status | Notes |
|---|---|---|---|---|
| Next.js scaffold (App Router, TS, Tailwind, shadcn init, 3-col layout shell, `/health` fetch) | shubhodeep | main (orchestrated) | wip | Dispatched 2026-05-23 — non-overlapping with backend |
| FastAPI scaffold (project layout, `/health`, CORS, pyproject.toml, stub modules) | codex (subagent) | main (orchestrated) | wip | Dispatched 2026-05-23 — non-overlapping with frontend |
| Repo root README | shubhodeep | main | wip | Done after subagents complete so it can reference real scaffold |
| Smoke-test doc skeleton (`docs/smoke-tests.md`) | shubhodeep | main | wip | Done in parallel with subagents |

---

## Ready to claim

Tasks with no unresolved dependencies. Pick one, move it to In progress, then start work.

| Task | Phase | Dependencies | Estimate |
|---|---|---|---|

_(P0 tasks all claimed — see In progress)_

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
| MVP slice design (this spec) | pre-P0 | 2026-05-23 | `docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md` |
| AGENTS.md created | pre-P0 | 2026-05-23 | initial seed |
| PROJECT_TRACKER.md created | pre-P0 | 2026-05-23 | initial seed |

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

---

## Phase backlog

### P0 — Scaffold

Goal: both servers run, frontend → backend smoke test passes.

- [ ] Repo root README + .gitignore
- [ ] Next.js init in `frontend/` (App Router, TS strict, Tailwind, shadcn/ui base)
- [ ] FastAPI init in `backend/` (pyproject.toml with httpx + biopython + pydantic + fastapi + uvicorn, `app/main.py` with CORS, `/health` endpoint)
- [ ] Frontend `lib/api.ts` calls `/health` and renders status on landing page
- [ ] `docs/smoke-tests.md` with the P0 smoke test recorded

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
