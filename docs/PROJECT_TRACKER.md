# Project Tracker

**Project:** AI-Powered Protein Structure Visualization Platform
**Living document.** Read before claiming work. Update on claim, on PR open, on merge.

**Last updated:** 2026-08-18 by Shubhodeep Chatterjee (final-review fix pass done — CRITICAL pLDDT inversion plus all five important findings, on `feature/fix-plddt-inversion-and-final-review`. 90 backend + 103 frontend tests green, lint + build clean; every new test verified by mutation. MVP slice P0-P5 feature-complete pending the manual smoke tests, which now include a P5.5 section for these fixes.)

---

## Current phase

**Slice complete (P0–P5)** — all six phases merged. Remaining work is the manual smoke tests in [docs/smoke-tests.md](smoke-tests.md), which need a browser and live internet.

Active design: [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](superpowers/specs/2026-05-23-protein-mvp-slice-design.md)

---

## In progress

_Nothing in flight. The final-review fix pass is merged-ready on `feature/fix-plddt-inversion-and-final-review`; remaining work is the manual smoke tests._

| Task | Owner | Branch | Status | Notes |
|---|---|---|---|---|

---

## Ready to claim

Follow-ups discovered during P4/P5. None block the slice; each was deliberately deferred with a reason.

| Task | Phase | Dependencies | Estimate |
|---|---|---|---|
| Run the P4 + P5 + **P5.5** manual smoke tests (browser + live internet required) | P5.5 | — | 1h |
| B-factor coloring of experimental structures is no longer reachable — the one toolbar option that drove it is now gated on `has_plddt`. Wants its own `bfactor` scheme (same `uncertainty` theme, default domain) rather than sharing the pLDDT entry. | follow-up | — | 45m |
| `_extract_mmcif_organism` takes the first source category that has a value; a multi-entity mmCIF with different organisms per entity reports only the first. Fine for the single-protein viewer, wrong for a future complex/assembly view. | follow-up | — | 1h |
| `tests/fixtures/1CRN.cif` is `_atom_site`-only, single-chain, 1-based — exercises none of the mmCIF shape that could break the residue seam | test | — | 45m |
| Dedupe backend constants: 50 MB ceiling defined twice, `_ALLOWED_EXTS` twice with different members, store->parse->register->unlink flow duplicated | cleanup | — | 1h |
| `viewer-slice` representation/coloring never reset across proteins (selection is) | fix | — | 20m |
| `proteins.py:64` `detail=str(exc)` can leak the storage path from an OSError (pre-existing; the P5 import path is already generic) | fix | — | 20m |
| Add a `"uniprot"` member to `ProteinSummary.source` so a UniProt-card import keeps its provenance | follow-up | shared model change | 45m |
| Derive the AlphaFold fallback file URL from `latestVersion` instead of the hard-coded `-model_v4.pdb` | follow-up | — | 30m |
| Batch RCSB search enrichment via the GraphQL Data API (currently up to 50 REST calls per search) | follow-up | — | 2h |
| Retries / backoff / rate limiting on the three outbound clients | follow-up | — | 2h |
| Virtualise the sequence panel (one `<button>` per residue gets heavy above ~2,000 residues) | follow-up | — | 2h |
| Make HETATM amino acids (e.g. MSE) selectable — currently skipped consistently by both parser and panel | follow-up | — | 1h |
| Browser-level coverage for `extractResidueRecords` (the Mol\*-facing half of residue indexing, untestable in jsdom) | follow-up | a browser test runner | 3h |
| Persistence slice — the in-memory registry resets on restart, so `/viewer/{id}` 404s afterwards though the file survives on disk | separate slice | Postgres decision | — |

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
| P4: `sequence-panel.tsx` + `sequence-chain.tsx` (per-chain grid, residue-type colouring, legend, position ruler, scroll-to-selected) | P4 | 2026-08-18 | `712bfd6` |
| P4: `highlightResidues` + real `setRepresentation` / `setColoring`; 3D-click -> store via `onResidueClick`; ordinal<->Mol\* residue-index mapping in `lib/residue-map.ts` | P4 | 2026-08-18 | `712bfd6` |
| P4: `A:123` residue search (`parseResidueQuery`), tabbed Overview / Sequence / Analytics rail, viewer page decomposed into 10 components | P4 | 2026-08-18 | `712bfd6` |
| P4 review round 1: ligand click no longer clears selection; all four page-local flags reset on route change; numbering convention pinned by a non-1-based gapped multi-chain fixture; load-staleness guards | P4 | 2026-08-18 | `290eba1`, `11dfdd0`, `448c6ad` |
| P4 review round 2: `source` pinned as the residue sort key (prior test passed under mutation) | P4 | 2026-08-18 | `8e6c6c6` |
| P5: `services/registry.py` extracted from the proteins router so imports and uploads share one store | P5 | 2026-08-18 | `819167f` |
| P5: real RCSB / AlphaFold / UniProt clients behind one uniform interface, `services/external.py` + `services/cache.py` (LRU 256 / TTL 1h) | P5 | 2026-08-18 | `819167f` |
| P5: `GET /api/search` fan-out with dedupe + `failed_sources` degradation; `POST /api/proteins/import` returning the upload `ProteinSummary` shape | P5 | 2026-08-18 | `819167f` |
| P5: `/search` page (source filter, result cards, per-card import state, failed-source banner) + 43 backend / 10 frontend tests, all external HTTP mocked | P5 | 2026-08-18 | `819167f` |
| P5 review rounds 1-2: cache scope split, AlphaFold status classification reworked so a transport error can never read as "no model", search request sequencing | P5 | 2026-08-18 | `a8c1cd8`, `11301a7`, `ffab9cc`, `42f4b64` |
| P4 + P5 smoke tests written in `docs/smoke-tests.md`; decisions log extended with 7 entries | P4/P5 | 2026-08-18 | `005bea1`, `d04beb6` |
| **CRITICAL** — pLDDT color inversion fixed: `colorParams { domain: [100, 0] }` on the shared `uncertainty` theme, so high confidence reads blue. Orientation pinned against Mol\*'s real `ColorScale`; `ColoringOptions.hasPlddt` made required so a dropped call-site argument is a type error | review | 2026-08-18 | `61648dc` |
| Organism now read from the mmCIF source categories (`_entity_src_gen` / `_entity_src_nat` / `_pdbx_entity_src_syn` / `_ma_target_ref_db_details`), skipping the `?` and `.` null tokens — every RCSB import used to parse to `organism=None` | review | 2026-08-18 | `fb6ff33` |
| `has_plddt` surfaced in the UI: pLDDT coloring offered only when true, explicit fallback for a stale selection carried across navigation, and a "B-factors" field in the Overview panel | review | 2026-08-18 | `712d8b2` |
| `search-view.tsx` split 226 -> 124 LOC (`search-form.tsx` + `search-results.tsx`); `molstar-viewer.tsx` 210 -> 189 LOC (`lib/molstar/plugin.ts`) — both now under the AGENTS.md 200-LOC cap | review | 2026-08-18 | `d49a6d9` |
| Landing page + README stopped denying shipped features ("P2" badge, disabled Upload button, "arrives in P4" / "arrive in P3" panel copy) | review | 2026-08-18 | `460b4e4` |
| P5.5 smoke test added: residue click on an IMPORTED RCSB mmCIF, organism round-trip, pLDDT orientation, and `has_plddt` gating | review | 2026-08-18 | `2b65a74` |

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
| 2026-08-18 | In-memory summary registry extracted to `services/registry.py` | Import and upload must register into the SAME store the viewer reads, or an imported protein 404s. A router importing another router's private dict is fragile. | yes |
| 2026-08-18 | AlphaFold search resolves via UniProt with a `(database:alphafolddb)` filter | AlphaFold DB has no full-text search endpoint at all — it is keyed strictly by UniProt accession. Filtering at UniProt is 1 request and guarantees every hit has a model; probing 25 accessions costs 25 round trips for one display field. Trade-off: mean pLDDT is null on search results, populated on fetch_metadata. | yes |
| 2026-08-18 | Metadata TTL cache split: `download_structure` bypasses it, search enrichment keeps it | Spec 5.4 says search and download bypass the cache. A stale cached `pdbUrl` is a real failure, so download must bypass. But each search enrichment IS a `fetch_metadata` call, and bypassing would mean up to 50 uncached upstream calls per RCSB search. | yes |
| 2026-08-18 | A transport error on an external leg can never classify as 404 | A connection failure teaches us nothing about whether a model exists. Only a 404 on the published/authoritative URL means "no model"; everything else upstream is 502. | yes |
| 2026-08-18 | UniProt imports are stored as `source: "alphafold"` | `ProteinSummary.source` has no `"uniprot"` member (spec 5.1) and a UniProt import literally downloads the cross-referenced AlphaFold model. Truthful, and keeps `has_plddt` correct. Cost: the viewer cannot show that the user arrived via a UniProt card. | yes — add a `"uniprot"` member if provenance matters |
| 2026-08-18 | Residue keys are `chain:ordinal` (1-based within chain), NOT `auth_seq_id` | PDB files can start at any residue number and contain gaps and insertion codes. The frontend mirrors the backend parser's filter and maps ordinal to Mol*'s model residue index. Pinned by tests against a non-1-based, gapped, multi-chain fixture. | hard — changing it breaks selection sync in both directions |
| 2026-08-18 | A click on unindexed 3D geometry (ligand, water) preserves the selection | A cofactor is real geometry that simply has no sequence cell; only genuinely empty space clears the selection. These were previously conflated as `null`. | yes |
| 2026-08-18 | pLDDT keeps riding Mol\*'s `uncertainty` theme, with the domain inverted to `[100, 0]` rather than switching themes | The dedicated `plddt-confidence` theme lives in the model-archive extension and needs the mmCIF `ma_qa_metric_local` category, which AlphaFold *PDB* downloads do not carry — so it would work for some AlphaFold imports and not others. Inverting the domain is one parameter and works for both file formats. | yes |
| 2026-08-18 | `ColoringOptions.hasPlddt` is required, not optional with a `false` default | The shipped bug was an implicit assumption that the B-factor column means the same thing for every structure. A required field turns a dropped call-site argument into a compile error — verified by mutation: removing it from the viewer page fails `tsc`, not just a test. | yes |
| 2026-08-18 | Organism for mmCIF is read from the raw category dict, not threaded through from the RCSB client | The parser must work for an *uploaded* mmCIF too, which has no RCSB metadata behind it. Reading the categories fixes both paths at once and keeps the parser self-contained. Cost: the fallback chain takes the first entity's organism (follow-up filed). | yes |
| 2026-08-18 | pLDDT coloring is hidden rather than relabelled on structures without pLDDT | Offering "pLDDT confidence" on an X-ray entry advertises a score that structure does not have. Cost: B-factor coloring of experimental structures is no longer reachable, since one option served both — follow-up filed to give it its own `bfactor` scheme. | yes — the option list is one function |

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

- [x] `services/analytics.py` (MW, composition, hydrophobicity, SS%, property distribution)
- [x] `GET /api/proteins/{id}/analytics`
- [x] Metric cards (MW, residues, atoms, chains)
- [x] Composition bar chart (Recharts)
- [x] SS donut chart
- [x] Hydrophobicity line chart (Kyte-Doolittle, window 9)
- [x] Chain length bar chart
- [x] Backend pytest: MW + composition for crambin
- [x] P3 smoke test

### P4 — Sequence panel

Goal: bidirectional click sync between sequence and 3D.

- [x] `SequencePanel.tsx` (per-chain, color by residue type)
- [x] Zustand `selectionSlice`
- [x] Mol* selection event → store dispatch
- [x] Store subscribe → Mol* `highlightResidues`
- [x] Residue search input (`A:123` syntax)
- [x] Frontend Vitest: selection reducer tests
- [x] P4 smoke test

### P5 — DB search + import

Goal: search "insulin", click a result, see it in the viewer.

- [x] `services/rcsb.py` (search, fetch_metadata, download_structure)
- [x] `services/alphafold.py` (search via UniProt cross-ref, fetch model)
- [x] `services/uniprot.py` (search, fetch_metadata)
- [x] `GET /api/search?q=&source=` with `asyncio.gather` fan-out + dedupe
- [x] `POST /api/proteins/import`
- [x] `app/search/page.tsx` (search input, result cards, source filter)
- [x] Backend pytest: each client with recorded HTTP fixtures (respx / pytest-httpx)
- [x] P5 smoke test

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
