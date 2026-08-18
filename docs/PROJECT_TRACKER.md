# Project Tracker

**Project:** AI-Powered Protein Structure Visualization Platform
**Living document.** Read before claiming work. Update on claim, on PR open, on merge.

**Last updated:** 2026-08-18 by Shubhodeep Chatterjee (P4 + P5 claimed and dispatched in parallel worktrees — final two phases of the MVP slice)

---

## Current phase

**P4 — Sequence panel** and **P5 — DB search + import** (both in flight; P0–P3 complete)

Active design: [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](superpowers/specs/2026-05-23-protein-mvp-slice-design.md)

---

## In progress

Both remaining phases are claimed. They touch disjoint files (P4 = frontend selection/sequence; P5 = backend external clients + search page), so they run in parallel worktrees per AGENTS.md §5.

| Task | Owner | Branch | Status | Notes |
|---|---|---|---|---|
| P4: sequence panel + bidirectional Mol\* selection sync (SequencePanel, selectionSlice wiring, `highlightResidues`, residue search, vitest) | shubhodeep | `feature/p4-sequence-panel` | wip | Owns `frontend/components/sequence/*`, `molstar-viewer.tsx`, `selection-slice.ts`, `app/viewer/[id]/page.tsx` |
| P5: RCSB + AlphaFold + UniProt clients, `GET /api/search`, `POST /api/proteins/import`, search page (respx-mocked pytest) | shubhodeep | `feature/p5-db-search-import` | wip | Owns `backend/app/services/{rcsb,alphafold,uniprot}.py`, `api/{search,import_}.py`, `main.py`, `app/search/page.tsx` |

---

## Ready to claim

_Empty — every task in the P0–P5 slice is either done or in flight. New follow-ups discovered during P4/P5 land here._

| Task | Phase | Dependencies | Estimate |
|---|---|---|---|

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
| MVP slice design | pre-P0 | 2026-05-23 | `5f5d66a` |
| AGENTS.md created | pre-P0 | 2026-05-23 | `5f5d66a` |
| PROJECT_TRACKER.md created | pre-P0 | 2026-05-23 | `5f5d66a` |
| Repo `.gitignore` (root) | P0 | 2026-05-23 | `5f5d66a`, refined in `244e73f` |
| Repo root `README.md` | P0 | 2026-05-23 | `244e73f` |
| `docs/smoke-tests.md` skeleton with P0 verification script | P0 | 2026-05-23 | `244e73f` |
| Next.js scaffold (Next 16 + TS strict + Tailwind v4 + shadcn + Zustand v5, 3-col layout shell, HealthPill, lib/api, store slices, Vitest with 7/7 tests) | P0 | 2026-05-23 | `244e73f` |
| FastAPI scaffold (FastAPI 0.110+ + Python 3.11+ + pyproject, CORS, /health, Pydantic ProteinSummary, stub modules for parser/analytics/rcsb/alphafold/uniprot/storage, pytest test_health passing) | P0 | 2026-05-23 | `244e73f` (Codex subagent) |
| P0 integration smoke test (backend venv install, both servers up, /health returns ok, CORS preflight allows :3000, frontend serves shell HTML with all expected layout strings) | P0 | 2026-05-23 | `e386c0a` |
| P1: 1CRN.pdb bundled in `backend/app/static/`; `GET /api/proteins/demo/file` returns chemical/x-pdb; 3 pytest tests pass | P1 | 2026-05-24 | `e411039` |
| P1: `MolstarViewer.tsx` forwardRef component (Mol* 5.9.0, `loadStructure`, `resetCamera`, `setRepresentation`, `setColoring`); `/viewer/demo` page with toolbar + loading/error overlay; Next.js build + lint + 7/7 tests green | P1 | 2026-05-24 | `bac1f80` |
| P1: smoke test written in `docs/smoke-tests.md`; tracker updated to P2 | P1 | 2026-05-24 | `110bfdd` |
| P2: BioPython parser → `ProteinSummary` (PDB + mmCIF, 1CRN parses to 46 residues / 1 chain / ~4737 Da MW) | P2 | 2026-05-24 | `9c0d08d` |
| P2: UUID-keyed local file storage (`backend/storage/proteins/`) with allowed-extension allowlist | P2 | 2026-05-24 | `9c0d08d` |
| P2: `POST /api/proteins/upload`, `GET /api/proteins/{id}`, `GET /api/proteins/{id}/file` + in-memory summary cache; 10 pytest tests (parser × 4, upload × 6) pass | P2 | 2026-05-24 | `9c0d08d` |
| P2: `DropZone.tsx` (drag-and-drop + click-to-browse, extension/size validation, inline errors, multipart upload via `apiPost`) + 6 vitest tests | P2 | 2026-05-24 | `1a03651` |
| P2: `/viewer/[id]` dynamic-route page (fetches summary, renders Mol\*, 404 fallback, metadata toggle); landing page DropZone replaces placeholder; `protein-slice` wired to real API | P2 | 2026-05-24 | `1a03651` |
| P2: smoke test written in `docs/smoke-tests.md`; tracker updated to P3 | P2 | 2026-05-24 | this commit |
| Deepscan audit + fixes (path traversal, CORS hardening, race conditions, viewerReady reset, responsive layout, pytest cleanup fixture) | P2.5 | 2026-05-24 | `6a9cea6` + `d57b2ba` + `2f01f20` |
| P3: `services/analytics.py` pure functions (MW, composition, Kyte-Doolittle, SS%, property distribution) + Pydantic `AnalyticsResponse` | P3 | 2026-05-25 | `02f24d8` |
| P3: `GET /api/proteins/{uid}/analytics` via `run_in_threadpool` + 17 pytest tests (crambin MW ~4736, 6 cysteines, 38 hydrophobicity windows, SS sums to 1) | P3 | 2026-05-25 | `02f24d8` |
| P3: AnalyticsPanel.tsx + 4 Recharts charts (composition bar, SS donut, hydrophobicity line, chain-length bar) + metric cards in `/viewer/[id]` split layout | P3 | 2026-05-25 | `25453a4` |
| P3: smoke test written in `docs/smoke-tests.md`; tracker updated to P4 | P3 | 2026-05-25 | this commit |

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
- [x] Integration smoke test: backend venv built, both servers up; backend `/health` returns ok, CORS preflight allows `:3000`, frontend on `:3000` serves the shell HTML with all expected layout strings (ProteoLens, Mol, Chains, Sequence, Analytics, Overview, Upload). The actual green-pill render in a browser is a 30-second manual visit to `http://localhost:3000` — not automated because the pill is client-rendered.

### P1 — Static viewer

Goal: open `/viewer/demo` and rotate a real 3D crambin.

- [x] Bundle 1CRN PDB in `backend/app/static/`
- [x] `GET /api/proteins/demo/file` serves the bundled file
- [x] `MolstarViewer.tsx` component with `loadStructure`, `setRepresentation`, `setColoring`, `resetCamera` imperative API
- [x] `/viewer/demo` page using the wrapper
- [x] P1 smoke test in `docs/smoke-tests.md`

### P2 — Upload + parse

Goal: drag a PDB onto the home page → see it render.

- [x] `DropZone.tsx` with client-side validation (extension, size)
- [x] `services/parser.py` (BioPython, returns `ProteinSummary`)
- [x] `services/storage/local.py` (UUID-keyed)
- [x] `models/protein.py` (Pydantic ProteinSummary, ChainInfo)
- [x] `POST /api/proteins/upload`
- [x] `GET /api/proteins/{id}` (returns ProteinSummary)
- [x] `GET /api/proteins/{id}/file` (binary)
- [x] Frontend `/viewer/[id]` page loads from API
- [x] Backend pytest: 1CRN parser test
- [x] P2 smoke test

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
