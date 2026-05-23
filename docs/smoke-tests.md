# Smoke Tests

Per-phase manual checks. An agent claims a phase "Done" in `PROJECT_TRACKER.md` only when the corresponding smoke test passes — type-check and unit tests alone are not enough.

Run from the repo root (`g:\protein`) unless noted.

---

## P0 — Scaffold

**Goal:** both servers start and the frontend successfully calls the backend.

1. Backend: open a terminal, run
   ```
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1        # PowerShell  (or source .venv/bin/activate on bash)
   pip install -e ".[dev]"
   uvicorn app.main:app --reload --port 8000
   ```
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

_Will be filled in when P3 starts._

---

## P4 — Sequence panel

**Goal:** clicking a residue in the sequence panel highlights it in 3D, and clicking a residue in 3D scrolls + highlights it in the sequence panel.

_Will be filled in when P4 starts._

---

## P5 — DB search + import

**Goal:** searching "insulin" returns merged results from RCSB + AlphaFold + UniProt; clicking import lands the user in the viewer with that structure rendered.

_Will be filled in when P5 starts._

---

## How to add a smoke test

When you start a phase, replace the placeholder for that phase with the concrete steps. The steps should be the minimum sequence a fresh agent or human needs to verify the phase works end-to-end, including:

- Setup commands (idempotent)
- Expected outputs (exact strings or close)
- Negative cases (what should fail gracefully — e.g. backend down)
- Test commands (`pytest`, `npm test`)

Keep each phase ≤ 10 steps. If it gets longer, split into multiple smoke tests.
