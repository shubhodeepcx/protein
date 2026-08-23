# Smoke Tests

Per-phase manual checks. An agent claims a phase "Done" in `PROJECT_TRACKER.md` only when the corresponding smoke test passes — type-check and unit tests alone are not enough.

Run from the repo root (`g:\protein`) unless noted.

---

## Last verified run — 2026-08-21

P0–P5.5 executed end-to-end in a real Chromium (driven by Playwright) against both servers running
locally and against the **live** public APIs. Results:

| Check | Result |
|---|---|
| Landing page, `Backend OK` pill, Databases link, Upload enabled | pass |
| Mol\* WebGL renders 1CRN at `/viewer/demo` | pass — cartoon, helices and sheets resolved |
| Upload `1CRN.pdb` → `/viewer/{uuid}` | pass |
| Overview metrics | pass — chains 1, residues 46, atoms 327, MW 4736 Da |
| Sequence panel | pass — 46 cells, `TTCCPSIVARSN`, labels A:1–A:46, legend + ruler |
| Sequence → 3D click sync | pass — A:23 boxed as `E`, highlight visible in the viewport |
| Residue search | pass — `a:7` → `I`; `A:999` → "No residue A:999 — chain A has 46 residues" |
| `has_plddt` gating | pass — pLDDT option **absent** on uploaded PDB, **present** on AlphaFold import |
| Live search `insulin` | pass — 75 results, 25 each from RCSB / AlphaFold / UniProt, `failed_sources` empty |
| Import 4INS (multi-chain **mmCIF**) from live RCSB | pass — A21/B30/C21/D30, organism `Sus scrofa` |
| **Residue seam on imported mmCIF** | pass — ordinals restart per chain; B:25 boxed as `F` with 3D highlight |
| Import AlphaFold P01308 | pass — `has_plddt: true`, 110 residues |
| **pLDDT coloring direction** | pass — confident helix renders **blue**, disordered loop pink (correct convention) |
| AlphaFold 404 path | pass — `Q0Q0Q0` → 404 "AlphaFold DB has no model for accession 'Q0Q0Q0'." |

**Human-confirmed the same day** (the three checks that need a mouse on a 3D canvas, which the
automated pass could not aim at):

| Check | Result |
|---|---|
| 3D → sequence direction: clicking the ribbon boxes a letter, and a different click boxes a different letter | pass |
| 1HHO cofactor: selection **survives** a click on a HEM group; a background click **clears** it | pass |
| Mouse rotate + scroll zoom | pass |

That completes both directions of the P4 click-sync and the ligand-vs-background distinction, which
were the last behaviours resting only on static review.

Still not covered: the offline-source degradation banner in P5 step 9 — it needs a host blocked at
the firewall/hosts level. The equivalent path is covered by an automated backend test (a raising
source returns 200 with that source in `failed_sources`), so this is UI confirmation only.

---

## P0 — Scaffold

**Goal:** both servers start and the frontend successfully calls the backend.

1. Backend: open a terminal, run
   ```
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1        # PowerShell  (or source .venv/bin/activate on bash)
   pip install -e ".[dev]"
   $env:CORS_ORIGINS="http://localhost:3000"   # PowerShell  (bash: export CORS_ORIGINS=http://localhost:3000)
   uvicorn app.main:app --reload --port 8000
   ```
   - `CORS_ORIGINS` is required — see `backend/.env.example`. Without it the frontend will fail browser preflight.
   - Expect: server reports `Uvicorn running on http://127.0.0.1:8000`.
   - Visit `http://localhost:8000/health` → JSON `{"status": "ok", "service": "protein-backend", "version": "0.1.0"}`.
   - Visit `http://localhost:8000/docs` → Swagger UI loads.
2. Frontend: open a second terminal, run
   ```
   cd frontend
   npm install
   npm run dev
   ```
   - Expect: Next.js reports `Ready in …` on port 3000.
   - Visit `http://localhost:3000/` → page loads with header, 3-column layout shell, and a green "Backend OK" pill (because the page fetched `/health`).
3. Stop the backend; reload the frontend page.
   - Expect: the pill flips to red "Backend unreachable" with no crash.
4. Backend tests:
   ```
   cd backend
   pytest
   ```
   - Expect: `test_health` passes.
5. Frontend tests:
   ```
   cd frontend
   npm test
   ```
   - Expect: the selection-slice smoke test passes.

**Pass criteria:** all of the above without errors.

---

## P1 — Static viewer

**Goal:** open `/viewer/demo` and rotate a real 3D crambin structure.

1. Start backend (if not running):
   ```
   cd backend
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --port 8000
   ```
   - Visit `http://localhost:8000/api/proteins/demo/file` → browser downloads `1CRN.pdb` (~49 KB).

2. Start frontend (if not running):
   ```
   cd frontend
   npm run dev
   ```
   - Visit `http://localhost:3000/viewer/demo` → page loads with dark toolbar (ProteoLens / 1CRN — Crambin / P1 badge).
   - Loading spinner appears briefly, then the Mol\* canvas renders crambin in cartoon representation.
   - Drag to rotate, scroll to zoom — structure moves responsively.
   - Click **surface**, **stick**, **ball-stick**, **spacefill** → active button highlights.
   - Click the reset-camera (↺) button → structure re-centers.

3. Stop the backend; reload `/viewer/demo`.
   - Expect: "Could not load demo structure. Is the backend running?" overlay — no crash.

4. Backend tests:
   ```
   cd backend
   pytest
   ```
   - Expect: `test_demo_file` (3 tests) + `test_health` = 4 passed.

5. Frontend tests:
   ```
   cd frontend
   npm test
   ```
   - Expect: 7/7 pass (Mol\* itself is exercised only in the browser).

**Pass criteria:** crambin renders and rotates in the browser; all automated tests pass.

---

## P2 — Upload + parse

**Goal:** drag a `.pdb` file onto the landing page → see it render with chain/residue counts.

1. Start backend (if not running):
   ```
   cd backend
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --port 8000
   ```

2. Start frontend (if not running):
   ```
   cd frontend
   npm run dev
   ```

3. Visit `http://localhost:3000/` → landing page shows the **DropZone** card with "Drop a .pdb or .cif file here" in the center column (no more placeholder).

4. Drag `backend/app/static/1CRN.pdb` onto the DropZone (or click "Choose file" and pick it).
   - Expect: card flips to "Uploading 1CRN.pdb…" with a spinner.
   - After 1–3 seconds, the browser navigates to `/viewer/{uuid}` and crambin renders in the Mol\* canvas.

5. On the viewer page, click "metadata" in the toolbar.
   - Expect: panel shows `chains: 1 (A)`, `residues: 46`, `atoms: 327`, `MW: ~4737`, `format: pdb`.

6. Negative cases on the landing page:
   - Drop a `.txt` file → inline red error: "Unsupported extension '.txt'. Allowed: .pdb, .cif, .mmcif".
   - Drop an empty file (e.g., `New-Item empty.pdb`) → inline error: "File is empty."

7. 404 path: visit `http://localhost:3000/viewer/does-not-exist`.
   - Expect: red "Protein does-not-exist not found" with "Upload a new protein" link back to `/`.

8. Backend tests:
   ```
   cd backend
   pytest
   ```
   - Expect: 14 passed (demo file × 3, health × 1, parser × 4, upload × 6).

9. Frontend tests:
   ```
   cd frontend
   npm test
   ```
   - Expect: 13 passed (selection-slice × 7, drop-zone × 6).

**Pass criteria:** real PDB uploaded → parsed → rendered in 3D; metadata panel shows correct chain/residue/atom/MW counts; validation errors fire; all automated tests pass.

---

## P3 — Dashboard

**Goal:** uploaded protein shows MW, residue count, atom count, composition bar chart, secondary-structure donut, hydrophobicity line, chain-length bar chart in the right panel.

1. Start backend (P0 instructions). Set `CORS_ORIGINS` first:
   ```
   cd backend
   $env:CORS_ORIGINS = "http://localhost:3000"
   uvicorn app.main:app --reload --port 8000
   ```
2. Start frontend:
   ```
   cd frontend
   npm run dev
   ```
3. Visit `http://localhost:3000` → drop `backend/app/static/1CRN.pdb` onto the DropZone → page navigates to `/viewer/{id}`.
4. Verify the right-side panel (visible at ≥1280px viewport; stacks below viewer at narrower widths):
   - **Metric cards**: MW ~4736 Da, Residues 46, Atoms 327, Chains 1.
   - **Amino-acid composition**: 20 blue bars; hovering Cys shows "6 (13.04%)".
   - **Secondary structure**: donut with three slices (helix ~46%, sheet ~17%, coil ~37% for 1CRN); legend below.
   - **Hydrophobicity**: green line spanning residue positions ~5–42 (window 9 on 46-residue chain → 38 points); horizontal reference line at y=0; range stays within −4.5 to 4.5.
   - **Chain lengths**: single purple bar labeled "A" at length 46.
5. Resize browser to <1024px: analytics panel moves below the viewer and remains fully scrollable.
6. Probe the API directly:
   ```
   curl http://localhost:8000/api/proteins/<uid>/analytics | jq .
   ```
   - Expect: `molecular_weight` in [4700, 4770], `composition` array of length 20, `hydrophobicity.values` length 38, `secondary_structure` sums to ~1.0.
7. Backend tests:
   ```
   cd backend
   pytest
   ```
   - Expect: 31 passed (17 analytics + 14 prior).
8. Frontend tests:
   ```
   cd frontend
   npm test
   ```
   - Expect: 13/13 pass (charts are exercised only in the browser).

**Pass criteria:** all four charts render with the expected shapes for 1CRN; metric cards show MW/Residues/Atoms/Chains accurately; automated tests pass.

---

## P4 — Sequence panel

**Goal:** clicking a residue in the sequence panel highlights it in 3D, and clicking a residue in 3D scrolls + highlights it in the sequence panel.

1. Start both servers as in P0 (backend on `:8000` with `CORS_ORIGINS` set, frontend on `:3000`).
2. Visit `http://localhost:3000` → drop `backend/app/static/1CRN.pdb` → land on `/viewer/{id}`.
3. Open the **Sequence** tab in the right rail. Verify:
   - One block for chain **A**, labelled with its residue count (**46**).
   - 46 monospace residue cells, colored by residue class, with a legend and a position ruler every 10.
   - Crambin's sequence starts `TTCCPSIVAR` — cell 1 is `T`, cell 3 is `C`.
4. **Sequence → 3D:** click residue `A:23`. The cell takes the selected style, and the corresponding
   residue highlights in the Mol\* viewport. Click it again to deselect; the 3D highlight clears.
5. **3D → sequence:** rotate the model, click a residue in the viewport. The matching sequence cell
   becomes selected **and scrolls into view**. Confirm the residue identity matches — click a
   cysteine in 3D and verify a `C` cell lights up (crambin has 6: positions 3, 4, 16, 26, 32, 40).
   This is the step that catches residue-numbering drift between Mol\* `auth_seq_id` and the panel's
   1-based index — if the wrong cell highlights, P4 is not done.
6. **Non-protein geometry must not clear the selection.** Import or upload a structure with a
   cofactor — `1HHO` (haemoglobin, HEM groups) is the reference case. Select any chain A residue,
   then click the **HEM cofactor** in the viewport: the selection must **survive**, because a
   ligand is real geometry that simply has no sequence cell. Then click empty background: *now*
   the selection clears. These two must behave differently.
   This step exists because the fix separating "no locus at all" from "locus not in the residue
   index" has no unit-testable path — Mol\* is a trusted library and is not unit-tested, so this
   is the only place that distinction is verified.
7. **Navigation after a failed load.** Open a viewer URL whose structure fails to load (e.g. a
   uuid whose file was deleted from `backend/storage/proteins/`), then navigate to a working
   protein. The new viewer must mount and render — no stale error overlay, no stuck spinner.
8. **Residue search:** type `A:23` in the search box → that residue becomes the sole selection and
   scrolls into view. Type `A:999` → inline error naming chain A's real length (46). Type `Z:1` →
   inline error for the unknown chain. Lowercase `a:23` must work.
9. **Viewer controls:** change representation (cartoon → surface → spacefill) and coloring scheme
   from the toolbar; the viewport updates each time. The selection survives a representation change.
10. Tests:
    ```
    cd frontend
    npm run lint     # tsc --noEmit, clean
    npm test
    npm run build
    ```
    - Expect: all pre-existing tests still pass, plus the `parseResidueQuery`, `SequencePanel`, and
      residue-map tests. The residue-map suite is the one that pins the ordinal convention against a
      non-1-based, gapped, multi-chain fixture — if someone swaps ordinal for `auth_seq_id`, it fails.

**Pass criteria:** selection round-trips in both directions with the *same* residue, a cofactor click
preserves the selection while a background click clears it, navigation recovers from a failed load,
the search box resolves and rejects correctly, and lint/test/build are all green.

---

## P5 — DB search + import

**Goal:** searching "insulin" returns merged results from RCSB + AlphaFold + UniProt; clicking import lands the user in the viewer with that structure rendered.

> This is the only phase that touches the public internet. The automated tests are fully mocked
> (respx / pytest-httpx); the manual steps below deliberately hit the real APIs.

1. Start both servers as in P0.
2. Visit `http://localhost:3000/search` (or follow the "Search databases" link from the landing page).
3. Search `insulin`. Verify:
   - Results appear from more than one source, each card carrying a source badge (RCSB / AlphaFold /
     UniProt), a source id, a title, and an organism.
   - No duplicate `(source, source_id)` pairs in the list.
4. Use the source filter: selecting **RCSB** narrows results to RCSB only; **All** restores the merge.
5. **Import an RCSB entry** (e.g. `4INS`). The card shows a spinner, then the app routes to
   `/viewer/{id}` with the structure rendered in Mol\*, and the Analytics tab populates.
6. **Import an AlphaFold entry** (e.g. UniProt `P01308`). Verify the viewer loads it and the summary
   reports `has_plddt: true` — AlphaFold models carry pLDDT in the B-factor column.
7. **Graceful degradation:** stop the machine's network (or block `files.rcsb.org`) and search again.
   The request must still return **200** with whatever sources worked, and a non-blocking banner must
   name the sources in `failed_sources`. A single dead source must never fail the whole search.
8. **Import 404:** import an accession with no model (e.g. a UniProt entry AlphaFold has not
   predicted). Expect a 404 with a source-specific message surfaced inline on the card — not a crash.
9. Probe the API directly:
   ```
   curl "http://localhost:8000/api/search?q=insulin&source=all" | jq '.results | length, .failed_sources'
   curl -X POST http://localhost:8000/api/proteins/import \
        -H "Content-Type: application/json" -d '{"source":"rcsb","source_id":"4INS"}' | jq .
   ```
   - The import response must be the same `ProteinSummary` shape the upload endpoint returns, and the
     returned `id` must resolve on `GET /api/proteins/{id}` and `GET /api/proteins/{id}/file`.
10. Tests:
    ```
    cd backend && pytest
    cd frontend && npm run lint && npm test && npm run build
    ```
    - Expect: all pre-existing backend tests still pass alongside the new client / search / import
      tests, and the frontend suite stays green.

**Pass criteria:** a real search merges and dedupes across sources, a failing source degrades to a
banner instead of an error, import round-trips into a working viewer, and all tests pass offline.

---

## P5.5 — Final-review fixes

**Goal:** the three things the whole-branch review found that only a browser can confirm — pLDDT
renders the right way round, an imported RCSB **mmCIF** round-trips its organism *and* its residue
clicks, and the pLDDT coloring option only appears where pLDDT exists.

> P5 is already at the 10-step cap, and every step here needs a real import, so these live in their
> own section rather than growing that one.

1. Start both servers as in P0, then visit `http://localhost:3000/search`.

2. **Organism survives an mmCIF import.** Search `crambin`, note the organism printed on the RCSB
   card (`Crambe hispanica subsp. abyssinica` for `1CRN`), then import that card. On `/viewer/{id}`
   open the **Overview** tab: **Organism** must show that same value.
   Before the fix it read `Unknown` on every RCSB import — RCSB serves mmCIF, and BioPython's mmCIF
   header carries no source category at all, so the parser had nothing to read. Any RCSB entry works;
   what matters is that the viewer agrees with the search card that produced it.

3. **Residue click on an imported mmCIF.** Staying on that imported structure, repeat P4 steps 4 and
   5 — sequence cell → 3D, and 3D → sequence cell — and confirm the *same* residue lights up in both
   directions.
   This is the step P4 could not cover: it only ever exercised an **uploaded** `1CRN.pdb`. mmCIF
   reaches Mol\* through a different parser and carries `label_seq_id` alongside `auth_seq_id`, so
   the ordinal ↔ residue-index seam is genuinely a different code path here. Pick a residue well
   into the chain (not position 1) — an off-by-one seam looks correct at the start of a chain.
   For a multi-chain entry (`4INS` has chains A–D), click a residue on chain **C** or **D**: a seam
   that indexes across chains instead of within one only shows up past the first chain.

4. **pLDDT is not inverted.** Import an AlphaFold model — UniProt `P69905` (haemoglobin α) is the
   reference case — and pick **pLDDT confidence** from the coloring select.
   The confident core must render **blue** and the disordered tails **orange/red**. If the core is
   red, the domain inversion has been lost and the viewer is showing users the exact inverse of the
   AlphaFold convention. Cross-check one residue against the AlphaFold DB entry page for `P69905`,
   which uses the same blue-to-orange banding.

5. **pLDDT is offered only where it exists.** On that same AlphaFold structure the coloring select
   lists **pLDDT confidence**, and the Overview tab's **B-factors** field reads
   `pLDDT confidence (0–100)`. Now open the imported RCSB entry from step 2: the select must **not**
   list pLDDT at all, and **B-factors** must read `Temperature factors`.

6. **A stale pLDDT selection cannot survive the trip.** With the AlphaFold structure still on pLDDT
   coloring, navigate straight to the RCSB entry (browser Back, or the search page and re-import).
   The select must land on **Chain** and the viewport must repaint accordingly — never a select
   showing one scheme while Mol\* renders another.

7. Probe the import directly, to separate a parser problem from a UI one:
   ```
   curl -X POST http://localhost:8000/api/proteins/import \
        -H "Content-Type: application/json" -d '{"source":"rcsb","source_id":"1CRN"}' \
     | jq '{organism, has_plddt, file_format}'
   ```
   - Expect: `organism` non-null, `has_plddt: false`, `file_format: "mmcif"`.

8. Tests:
   ```
   cd backend && pytest
   cd frontend && npm run lint && npm test && npm run build
   ```
   - Expect: 90 backend, 103 frontend, lint and build clean.

**Pass criteria:** an imported mmCIF shows its organism and round-trips residue clicks in both
directions; high pLDDT reads blue; the pLDDT option and the Overview B-factors field both follow
`has_plddt`; and a stale pLDDT selection falls back rather than desynchronising.

---

## P6 — Annotation panel

Goal: open a protein imported from UniProt, RCSB or AlphaFold and read real biological
annotation in the rail; open an uploaded file and be told plainly why there is none.

1. Start both servers (`start.cmd`, or the two dev commands).
2. Go to `/search`, search `insulin`, import the **UniProt P01308** card.
3. In the viewer rail, click the **Annotations** tab.
   - Expect: sections **Names & Origin**, **Function**, **Gene Ontology**, **Keywords**,
     **Subcellular Location**, **Disease**, **PTM / Processing**, **Cross-references**.
   - Expect **no** Catalytic Activity and **no** Transmembrane heading — insulin is neither an
     enzyme nor a membrane protein, and an empty section is the bug this phase fixes.
   - Names & Origin reads `Insulin` / `INS` / `Homo sapiens` / `INS_HUMAN`.
   - Gene Ontology is split under *Molecular function*, *Biological process*,
     *Cellular component*.
   - A Reactome id links out to `reactome.org/content/detail/...` in a new tab.
4. Import an enzyme with a membrane span — search `EGFR`, import the UniProt **P00533** card.
   - Expect: **Catalytic Activity** showing the reaction text with `EC 2.7.10.1` and a
     `RHEA:` link, and **Transmembrane** listing the 646–668 helical span between two
     topological domains.
5. Import an **RCSB** entry (e.g. `4INS`) and open Annotations.
   - Expect: annotations resolved, with the footer note naming how — "via its polymer entity"
     or "via UniProt's index".
6. Upload a plain local PDB (e.g. `backend/app/static/1CRN.pdb`) and open Annotations.
   - Expect: HTTP 200, no red error, and the message
     *"Uploaded structures carry no database identifier to map from."*
   - Negative case: this must never be a 500 or an error state.
7. Collapse and re-expand any section header — sections start expanded.
8. Tests:
   ```
   cd backend && pytest
   cd frontend && npm ci && npm run lint && npm test && npm run build
   ```
   - Expect: 166 backend, 155 frontend, lint and build clean.

**Pass criteria:** an entry with rich annotation fills the rail from UniProt; an entry without a
given category shows no heading for it; an upload explains itself instead of erroring.

---

## P7 — Comparison view (spec A3)

Goal: put an experimental structure and a predicted model of the same protein side by side, and
have every number on the page be either a measurement or an explicit statement that it is not.

1. Start both servers (`start.cmd`, or the two dev commands).
2. Go to `/search` and search `insulin`. One query returns both an **RCSB** experimental entry
   (e.g. `4INS`) and an **AlphaFold** prediction (`P01308`) — this is A3's headline case.
   Import **both**; note each viewer URL's id.
3. From either viewer, click **Compare** in the header.
   - Expect: `/compare?a=<that id>`, and a form asking for the second id with A pre-filled.
   - Paste the other id and submit.
4. Two Mol\* canvases render side by side, each labelled **A** / **B** with its source.
   - Rotate one. Expect: the other does not move — they are independent viewers.
   - Negative case: neither canvas may be blank, and the browser console must show **no**
     "createRoot() on a container that has already been passed to createRoot()" error. That
     duplicate-root error is what two viewers on one page used to cause.
5. Change **Representation** to `Surface`. Expect: both panes change together.
   - Open **Coloring**. Expect **neither** `pLDDT confidence` nor `B-factor` in the list —
     the two structures disagree about what their B-factor column holds, so one shared
     select cannot label it truthfully for both. Import two AlphaFold models instead and the
     option reappears.
6. Read the **Sequence alignment** section.
   - Expect four figures: Identity, Similarity, Alignment length, and Identity over the
     overlap. For 4INS vs P01308 the last is far higher than the first — the crystal form is a
     mature two-chain construct and the model is the full precursor, so the overhang is real.
   - The alignment prints in numbered 60-column blocks with a `|` / `+` / blank match line.
7. Read the **Structural superposition** section.
   - Expect an RMSD in Å with its alpha-carbon pair count, over the chains named in the note.
   - Negative case: if a caveat appears (twilight-zone identity, or a thin fit), it must be
     shown in amber beside the number, never omitted.
8. Read the diff tables. Expect Δ columns of the form `+23` / `−16` / `0`, never an unsigned
   difference, and the composition table sorted by largest difference with a "show all 20" toggle.
   - Expect an amber line under Secondary structure saying structure **B** declares none —
     an AlphaFold model has no assigned secondary structure, so its all-coil split is a
     placeholder rather than a measurement.
9. Negative case: open `/compare?a=<real id>&b=deadbeef`.
   - Expect: `Comparison failed (404): Protein B not found` — naming **which** side — plus the
     id form pre-filled so the bad id can be fixed in place. Not a blank page, not a 500.
10. Tests:
    ```
    cd backend && pytest
    cd frontend && npm ci && npm run lint && npm test && npm run build
    ```
    - Expect: 200 backend, 213 frontend, lint and build clean.

**Pass criteria:** two independent viewers render together without a duplicate-root error; the
alignment and RMSD agree about which chains they used; and every absent result — no alignment,
no RMSD, an unmatched chain, an unannotated secondary structure — states its reason on screen.

---

## How to add a smoke test

When you start a phase, replace the placeholder for that phase with the concrete steps. The steps should be the minimum sequence a fresh agent or human needs to verify the phase works end-to-end, including:

- Setup commands (idempotent)
- Expected outputs (exact strings or close)
- Negative cases (what should fail gracefully — e.g. backend down)
- Test commands (`pytest`, `npm test`)

Keep each phase ≤ 10 steps. If it gets longer, split into multiple smoke tests.
