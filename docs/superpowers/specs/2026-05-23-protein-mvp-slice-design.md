# MVP Slice Design — AI-Powered Protein Structure Visualization Platform

**Date:** 2026-05-23
**Source spec:** [docs/spec.md](../../spec.md)
**Source SDLC:** [docs/sdlc.md](../../sdlc.md)
**Source report:** [docs/project_report.md](../../project_report.md)
**Status:** Approved — ready for plan
**Owner:** Shubhodeep Chatterjee (@shubhodeepcx)

---

## 1. What this spec covers

This is the design for the **first deployable vertical slice** of the larger 6-month platform described in `docs/spec.md`. The full product spans 9 MVP features (F1–F9), 6 advanced features (A1–A6), and 4 stretch features (S1–S4). This slice carves out the subset that makes the product feel real and demoable end-to-end, deferring everything that adds scaffolding without immediate user-visible payoff.

### In scope
- Next.js (TS, App Router) frontend + FastAPI (Python 3.11) backend, monorepo at `g:\protein`.
- Mol* 3D viewer integrated in the frontend.
- PDB / mmCIF upload with BioPython server-side parsing.
- Protein analytics dashboard (molecular weight, residue composition, hydrophobicity, secondary-structure %, chain stats).
- Sequence panel synced with 3D viewer (click-to-highlight both directions).
- Public database search and import: RCSB PDB, AlphaFold DB, UniProt.
- Local file storage keyed by UUID under `backend/storage/proteins/`.

### Out of scope for this slice
- User accounts, projects, persistence (no Postgres, no auth this iteration).
- AI annotation assistant (F8) — added in a later slice.
- Mutation impact visualizer (A2), comparative view (A3), similarity search (A4), contact map (A6).
- Export system (F9, PDF/PNG/JSON/CSV) — added in a later slice.
- DSSP integration — secondary structure read from PDB HELIX/SHEET records only.
- Docker, CI/CD, deployment — local-only dev for now.

### Decisions made during brainstorming
| Decision | Rationale | Reversible? |
|---|---|---|
| Build a vertical MVP slice end-to-end (Approach A) | Tighter feedback loop than frontend-first or backend-first; demoable at every phase | yes |
| Next.js + FastAPI split per spec | Python needed for BioPython, DSSP later, Foldseek later | hard — affects all of backend |
| Skip auth + DB for this slice | Faster path to a working viewer + analytics; avoids weeks of auth/migration plumbing | yes — can add Postgres + auth as its own slice |
| Monorepo at `g:\protein` | Solo dev, easier to keep frontend/backend in sync | yes |
| Local commands, no Docker | Fastest setup; add Docker once we have services to compose | yes |
| Zustand for frontend state | Smaller than Redux, integrates cleanly with Mol*'s imperative API | yes |
| File storage = local disk, UUID-keyed | Trivial; no MinIO/S3 friction; swap later when deploying | yes |

---

## 2. Architecture

### 2.1 Project layout

```text
g:\protein\
├── frontend\          # Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui
│   ├── app\
│   │   ├── layout.tsx
│   │   ├── page.tsx                  # Landing / recent proteins
│   │   ├── viewer\[id]\page.tsx      # Per-protein workspace
│   │   └── search\page.tsx           # RCSB/AlphaFold/UniProt search
│   ├── components\
│   │   ├── viewer\MolstarViewer.tsx
│   │   ├── upload\DropZone.tsx
│   │   ├── dashboard\*               # Metric cards + Recharts
│   │   ├── sequence\SequencePanel.tsx
│   │   └── ui\*                      # shadcn primitives
│   ├── lib\
│   │   ├── api.ts                    # Backend HTTP client
│   │   └── store\                    # Zustand slices
│   ├── package.json
│   └── tsconfig.json
│
├── backend\           # FastAPI, Python 3.11, BioPython
│   ├── app\
│   │   ├── main.py                   # FastAPI entrypoint, CORS
│   │   ├── api\
│   │   │   ├── proteins.py           # POST /upload, GET /{id}, GET /{id}/analytics
│   │   │   ├── search.py             # GET /search
│   │   │   └── import_.py            # POST /import
│   │   ├── services\
│   │   │   ├── parser.py             # BioPython → ProteinSummary
│   │   │   ├── analytics.py          # MW, composition, hydrophobicity, SS%
│   │   │   ├── rcsb.py
│   │   │   ├── alphafold.py
│   │   │   └── uniprot.py
│   │   ├── models\protein.py         # Pydantic models
│   │   └── storage\local.py          # UUID-keyed filesystem storage
│   ├── tests\
│   ├── storage\proteins\             # Runtime — gitignored
│   ├── pyproject.toml
│   └── README.md
│
├── docs\
│   ├── spec.md                       # Source spec
│   ├── sdlc.md                       # Source SDLC
│   ├── project_report.md             # Source report
│   ├── PROJECT_TRACKER.md            # Living tracker — read + update on every task
│   ├── smoke-tests.md                # Per-phase manual test scripts
│   └── superpowers\specs\
│       └── 2026-05-23-protein-mvp-slice-design.md   # This file
│
├── AGENTS.md                         # Rules for AI contributors
└── README.md
```

### 2.2 Module boundaries

- **Frontend never parses PDB itself.** All structural metadata comes from the backend. Mol* loads files from `GET /api/proteins/{id}/file`.
- **Backend never touches a DB this iteration.** State is filesystem + per-process in-memory dict keyed by UUID. Restart loses state; that's acceptable for the slice.
- **External API clients are interface-uniform.** `rcsb.py`, `alphafold.py`, `uniprot.py` all expose `search(query) -> list[SearchResult]`, `fetch_metadata(id) -> dict`, `download_structure(id) -> bytes`. Adding InterPro / PDBe-KB later means a new sibling file — no caller changes.
- **Analytics is pure.** `services/analytics.py` takes a parsed structure object and returns numbers. No I/O, no API calls, easy to unit-test.

### 2.3 Communication

- Frontend at `http://localhost:3000`, backend at `http://localhost:8000`.
- CORS allowed for `localhost:3000` only.
- All endpoints are REST/JSON except file download (binary).
- No WebSocket / SSE yet; the import flow is fast enough to be synchronous.

---

## 3. Phase sequence

Each phase is independently demoable. Execution proceeds top-down; stopping after any phase leaves a coherent product.

| Phase | Frontend | Backend | Demo at end of phase |
|---|---|---|---|
| **P0 Scaffold** | Next.js + Tailwind + shadcn init, base 3-col layout shell | FastAPI init, `/health` endpoint, CORS | Both servers start, frontend successfully hits `/health` |
| **P1 Static viewer** | Mol* wrapper component, `/viewer/demo` page | Static-file route serves a bundled PDB (1CRN crambin) | Open `/viewer/demo` and rotate a real 3D protein |
| **P2 Upload + parse** | DropZone with client validation, post-upload redirect | `POST /api/proteins/upload` → BioPython parser → `ProteinSummary` | Drag a PDB, see your own protein render |
| **P3 Dashboard** | Metric cards + Recharts (composition bar, SS donut, hydrophobicity line, chain-length bar) | `GET /api/proteins/{id}/analytics` (MW, composition, Kyte-Doolittle hydrophobicity, SS% from PDB headers) | Upload → analytics appear beside viewer |
| **P4 Sequence panel** | Per-chain sequence view, color by residue type, click syncs with Mol* | No new endpoint (sequence already in `ProteinSummary`) | Click residue in sequence → highlight in 3D, and vice versa |
| **P5 DB search + import** | Search page with source filter, result cards, import button | `GET /api/search?q=…&source=all` fans out to all 3 sources via `asyncio.gather`; `POST /api/proteins/import` downloads + parses | Search "insulin", click a result, see it in the viewer |

**P0–P3 is the minimum that feels like a product.** P4–P5 complete the agreed scope. Beyond P5: AI assistant, mutation analysis, comparative view, export — separate slices.

---

## 4. Frontend design

### 4.1 Layout

Fixed top header (logo, global search box, upload button) → 3-column grid below:
- **Left** — collapsible sidebar with chain tree (expandable to residues), selection filters (by type / property / chain / range), and residue search.
- **Center** — Mol* viewer fills the available space; floating controls overlay for representation + coloring.
- **Right** — tabbed panel: **Overview** (metric cards) / **Sequence** (P4) / **Analytics** (Recharts).

### 4.2 State (Zustand)

Three slices, composed into one store:

- **`proteinSlice`** — current `ProteinSummary` (id, name, chains, residues, source). `loadProtein(id)` action fetches metadata.
- **`selectionSlice`** — `Set<string>` of selected residue keys (`"A:123"`), highlight color, selection mode (`single | range | type | property`). Action `toggleResidue(key)`.
- **`viewerSlice`** — Mol* representation (`cartoon | surface | stick | ball-stick | spacefill`), coloring scheme (`chain | ss | hydrophobicity | plddt | residueType`), camera reset trigger.

### 4.3 Mol* integration

One `<MolstarViewer>` React component owns the Mol* plugin instance. Exposes imperative ref API:
- `loadStructure(url: string, format: "pdb" | "mmcif")`
- `highlightResidues(keys: string[])`
- `setRepresentation(type)`
- `setColoring(scheme)`
- `resetCamera()`

Selection sync is bidirectional: Mol*'s selection events push into `selectionSlice`; `selectionSlice` subscriptions trigger `highlightResidues` calls. A single `useEffect` per direction prevents loops.

### 4.4 Charts

Recharts (per spec preference; smaller than Plotly, more idiomatic in React than ECharts):
- **Composition** — horizontal bar, 20 amino acids, % of total.
- **SS** — donut, helix / sheet / coil.
- **Hydrophobicity** — line chart, Kyte-Doolittle 9-window across the primary chain.
- **Chain length** — bar chart, one bar per chain.

---

## 5. Backend design

### 5.1 Core data shape

Every endpoint that returns a protein speaks `ProteinSummary`:

```python
class ChainInfo(BaseModel):
    id: str
    label: str               # "A", "B", …
    sequence: str            # one-letter codes
    residue_count: int

class ProteinSummary(BaseModel):
    id: str                  # UUID
    source: Literal["uploaded", "rcsb", "alphafold"]
    source_id: str | None    # PDB ID or UniProt accession
    name: str | None
    organism: str | None
    file_url: str            # /api/proteins/{id}/file
    file_format: Literal["pdb", "mmcif"]
    chains: list[ChainInfo]
    residue_count: int
    atom_count: int
    molecular_weight: float  # daltons
    has_plddt: bool
    warnings: list[str]
```

### 5.2 Parser (`services/parser.py`)

BioPython `MMCIFParser` for `.cif/.mmcif`, `PDBParser(QUIET=True)` for `.pdb`. Extracts:
- Chains and per-chain one-letter sequences (only standard 20 + non-standard via `IUPACData.protein_letters_3to1`).
- Per-residue properties (number, 3-letter and 1-letter code, property class, atom count).
- Atom totals.
- HELIX / SHEET records from the header (used as secondary-structure source — DSSP comes later).
- pLDDT presence (B-factor field on AlphaFold structures contains pLDDT in 0–100 range; we detect this if `source == "alphafold"`).
- Ligands and heteroatoms (HET records).

**Warnings appended**, not raised, for: missing atoms, multiple models (we take model 0), non-standard residues, chain breaks (gap > 1 in residue numbering).

### 5.3 Analytics (`services/analytics.py`)

Pure functions, no I/O. Inputs are the parsed structure or `ProteinSummary`. Outputs:
- `molecular_weight(seq)` — sum of average residue masses, minus `(n - 1) * water_mass`.
- `composition(seq)` — `{aa: count, %}` for all 20.
- `hydrophobicity_profile(seq, window=9)` — Kyte-Doolittle scale, sliding window average.
- `secondary_structure_percentages(structure)` — helix / sheet / coil percentages from HELIX/SHEET records.
- `property_distribution(seq)` — counts of hydrophobic / polar / charged-positive / charged-negative / aromatic / cysteine.

Known molecular weights for test proteins (crambin ≈ 4736 Da, insulin chain B ≈ 3429 Da) anchor the unit tests.

### 5.4 External clients

Same interface across `rcsb.py`, `alphafold.py`, `uniprot.py`:

```python
async def search(query: str) -> list[SearchResult]
async def fetch_metadata(id: str) -> dict
async def download_structure(id: str) -> tuple[bytes, str]  # (content, format)
```

- **RCSB** — Search API (POST to `https://search.rcsb.org/rcsbsearch/v2/query` with full-text query) → Data API (`https://data.rcsb.org/rest/v1/core/entry/{id}` for metadata) → file download from `https://files.rcsb.org/download/{id}.cif`.
- **AlphaFold** — `https://alphafold.ebi.ac.uk/api/prediction/{accession}` for metadata + file URL; structure at `https://alphafold.ebi.ac.uk/files/AF-{accession}-F1-model_v4.pdb`.
- **UniProt** — `https://rest.uniprot.org/uniprotkb/search?query=…&format=json` for search; `https://rest.uniprot.org/uniprotkb/{accession}.json` for metadata. UniProt returns sequence and points at AlphaFold/PDB cross-references; "downloading a structure" from UniProt means following the AlphaFold cross-ref.

All clients use `httpx.AsyncClient` with a 10-second timeout. In-memory LRU cache (size 256, TTL 1 hour) for metadata calls — search and structure download bypass the cache.

### 5.5 Storage (`storage/local.py`)

```python
def store_upload(file_bytes: bytes, ext: str) -> tuple[str, Path]:
    uid = uuid.uuid4().hex
    path = STORAGE_ROOT / f"{uid}.{ext}"
    path.write_bytes(file_bytes)
    return uid, path

def get_file(uid: str) -> Path:
    # validates uid is hex, joins with STORAGE_ROOT, rejects anything outside
```

Path traversal blocked by validating the UUID is pure hex before joining. Extensions are whitelisted (`pdb`, `cif`, `mmcif`). `storage/proteins/` is gitignored.

---

## 6. Data flow

### 6.1 Upload path

```
Browser
  → POST /api/proteins/upload (multipart, file)
  → validate (extension whitelist, size ≤ 50 MB, content sniff: first line is HEADER/data_)
  → store_upload(bytes, ext) → uuid, path
  → parser.parse(path) → ProteinSummary + warnings
  → in-memory cache[uuid] = ProteinSummary
  → response: { protein_id, file_url, summary, warnings }
Frontend
  → router.push(`/viewer/${protein_id}`)
  → MolstarViewer.loadStructure(file_url)
  → dashboard fetches GET /api/proteins/{id}/analytics
```

### 6.2 Import path

```
Frontend search page
  → GET /api/search?q=insulin&source=all
Backend
  → asyncio.gather(rcsb.search, alphafold.search, uniprot.search)
  → merge + dedupe by (source, source_id)
  → response: { results: [...], failed_sources: [...] }
Frontend
  → user clicks "Import" on a card
  → POST /api/proteins/import { source, source_id }
Backend
  → client.download_structure(source_id) → bytes, ext
  → store_upload(bytes, ext) → uuid, path
  → parser.parse(path) → ProteinSummary (source field = source)
  → cache[uuid] = ProteinSummary
  → response: same shape as upload
Frontend → /viewer/{id}
```

---

## 7. Error handling & validation

| Failure mode | Handling |
|---|---|
| Wrong extension / oversized file | Frontend rejects before upload; backend rejects with `400 { error, suggestion }` as defense-in-depth |
| Content sniff fails (not a PDB/CIF) | Backend `400 { error: "File does not look like PDB or mmCIF", suggestion }` |
| BioPython partial parse | `ProteinSummary` returned with `warnings` populated; **not** a 4xx — user sees the structure with caveats |
| BioPython total failure | `400` with error and the exception's first line as suggestion |
| Per-source external search failure | Search succeeds with whatever sources worked; failed sources listed in `failed_sources` array; frontend toast |
| Import 404 (e.g. AlphaFold has no model for accession) | `404` with source-specific message |
| Mol* load failure on frontend | Fallback card showing parser warnings + a "Re-download file" button |
| Backend down | Frontend banner: "Backend unreachable — make sure FastAPI is running on :8000" |

---

## 8. Testing strategy

### Backend (pytest)
- **Parser tests** — 1CRN (crambin) baseline, 1TRZ (insulin) for multi-chain, a deliberately truncated PDB for warnings, a non-PDB text file for rejection. Each is a fixture in `backend/tests/fixtures/`.
- **Analytics tests** — known MW for crambin (~4736 Da), composition counts hand-verified, Kyte-Doolittle sanity check on a known peptide.
- **External-client tests** — `respx` or `pytest-httpx` to mock HTTP. Recorded fixtures for one RCSB / AlphaFold / UniProt response each. Tests never hit the real API.
- **API tests** — FastAPI `TestClient`, upload-then-fetch-then-analytics round trip.

### Frontend (Vitest)
- Component tests: `DropZone` (validation messages), `SequencePanel` (click → state update), Zustand reducers.
- Mol* itself not unit-tested; treated as a trusted library.

### Manual smoke tests
- `docs/smoke-tests.md` lists the demo sequence for each phase (P0–P5). An agent claims a phase done only when its smoke test passes.

---

## 9. Project tracker

Living document at `docs/PROJECT_TRACKER.md`. Single source of truth for who is working on what. Both humans and AI agents read and update it.

### Required sections
- **Current phase** — which P# is active.
- **In progress** — task, owner, branch, status, notes.
- **Ready to claim** — task, phase, dependencies, estimate.
- **Blocked** — task, blocked-by, notes.
- **Done** — task, phase, merge date, PR link.
- **Decisions log** — append-only, with date, decision, rationale, reversibility.
- **Phase backlog** — checkboxed task list per phase P0–P5.

### Update rules
- Every task moves: `Ready → In progress → Done` (or `Blocked`).
- Claim by moving to In progress with owner + branch name **before** touching code.
- On PR open: status = `wip`. On merge: move to Done with PR link.
- Decisions log is append-only. Never edit past entries; supersede with a new entry referencing the old one.

The initial tracker is created with this design and seeded with P0–P5 task lists.

---

## 10. AI agent rules

Living document at `AGENTS.md` (repo root). Picked up automatically by Codex, Gemini, Cursor.

### What it contains
1. **Mandatory reading before any work** — `docs/spec.md`, `docs/sdlc.md`, `docs/PROJECT_TRACKER.md`, `AGENTS.md` itself, per-directory `AGENTS.md` if present.
2. **Claim-before-code rule** — agent updates the tracker to In progress with owner + branch **before** the first edit.
3. **Branch + commit conventions** — `feature/<phase>-<slug>`, commits authored by the repo owner, with `Co-Authored-By` footers for any AI agent that contributed (e.g. Codex). No `--no-verify`. No force-push to `main`.
4. **Coding standards** — TypeScript strict on frontend, full type hints on backend, components ≤ 200 LOC, Pydantic at API boundary, pure analytics functions.
5. **Definition of done** — code merged + phase smoke test passes + tracker Done with PR link + decisions log appended if architectural choice made.
6. **Parallel work etiquette** — independent tasks (separate phases / non-overlapping files) can be parallelized via worktrees and a reasoning-model + Codex split per the user's global preferences; cross-phase or shared-file work serializes.
7. **Destructive-action gate** — mirrors the user's #1 hard global rule. No `git reset --hard`, no `rm -rf` outside the agent's own worktree, no bulk-mutating scripts, no force-push without explicit in-turn user approval.
8. **Update protocol** — after non-trivial work, update tracker (status + Done column) and append to decisions log if a new architectural choice was made. This is the handoff for the next agent.

---

## 11. Open questions

None blocking. Things to revisit when their phase arrives:
- **DSSP integration** — currently deferred; will appear when we go beyond P3. If DSSP binary is not installable in the target environment, fall back to BioPython's `DSSP` (which still needs the binary) or `mkdssp` via Docker.
- **CORS in production** — set up when we go beyond local-only.
- **Auth + persistence slice** — separate spec when ready; will need migration of the in-memory cache to Postgres.
- **AI assistant slice** — separate spec; RAG over UniProt / InterPro / PDBe-KB annotations plus structural analytics.

---

## 12. Acceptance criteria for this slice

The slice is **done** when, on a clean clone:

1. `cd backend && uvicorn app.main:app --reload` starts the API on `:8000`.
2. `cd frontend && npm run dev` starts the UI on `:3000`.
3. Visiting `/viewer/demo` shows a 3D crambin structure that rotates and zooms smoothly.
4. Dragging a PDB file onto the home page lands the user in `/viewer/{id}` with the protein rendered.
5. The right-side dashboard shows MW, residue counts, composition bar chart, secondary-structure donut, and hydrophobicity line for the loaded protein.
6. Clicking a residue in the sequence panel highlights it in 3D; clicking in 3D scrolls + highlights in the sequence panel.
7. Searching "insulin" on `/search` returns merged results from RCSB + AlphaFold + UniProt, and importing any of them lands in the viewer.
8. `PROJECT_TRACKER.md` shows P0–P5 all in the Done section with PR links (or merge commits, since this is single-branch).
9. `pytest backend/tests` passes; `cd frontend && npm test` passes.
