# Project Tracker

**Project:** AI-Powered Protein Structure Visualization Platform
**Living document.** Read before claiming work. Update on claim, on PR open, on merge.

**Last updated:** 2026-08-24 by Shubhodeep Chatterjee (P6-P10 plus spec gaps A1 and A5 all merged. `main` at `5d1b271`: 533 backend / 433 frontend tests, tsc clean, webpack build clean. No known spec gaps remain.)

---

## Current phase

**P6-P10 complete and merged.** The annotation/comparison slice designed at
[2026-08-22-annotation-comparison-slice-design.md](superpowers/specs/2026-08-22-annotation-comparison-slice-design.md)
is fully shipped: annotations (P6), comparison (P7), BLAST + UniRef similarity (P8),
Complex Portal (P9) and interface density (P10). `main` is at `e06be37` with
**402 backend / 358 frontend** tests green, tsc clean and the webpack build clean.

BLAST was verified against the live EBI service on 2026-08-24 -- all four programs
(blastp, blastn, tblastn, blastx) ran real jobs end to end and returned biologically
correct results. See the decisions log.

_Previously:_ **Slice complete and verified (P0-P5).** All six phases merged, and the
manual smoke tests executed end-to-end in a real Chromium against live servers and live
public APIs.

Active design: [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](superpowers/specs/2026-05-23-protein-mvp-slice-design.md)

---

## In progress

| Task | Owner | Branch | Status | Notes |
|---|---|---|---|---|
| **Compounds: protein-related non-protein components.** Stop treating nucleic-acid-only chains as all-`X` protein chains; add `GET /api/proteins/{uid}/compounds` (nucleic-acid chains, ions, carbohydrates, cofactors/nucleotides, free amino acids, modified residues, crystallisation additives, ligands, each with its protein contact residues) and a Compounds tab in the viewer rail. User-requested scope expansion (2026-10-05) | shubhodeep | `feature/compounds` | wip | Protein `chains` stay protein-only so ordinals, analytics and selection are untouched |

---

## Ready to claim

Follow-ups discovered during P4/P5. None block the slice; each was deliberately deferred with a reason.

| Task | Phase | Dependencies | Estimate |
|---|---|---|---|
| **A5 Phase 2 — pocket *prediction*.** Phase 1 ships observed pockets only (residues within 4 A of a ligand in the file). An apo structure gets curated sites, surface and charge but no pocket, which is the honest answer and not a satisfying one. Phase 2 is a geometric detector (fpocket / LIGSITE style) or an ML scorer, and whatever it produces must be labelled a prediction and scored, never mixed into `ligands` | A5 | A5 merged | 1-2d |
| **A5 follow-up — cross-check the alignment against RCSB SIFTS.** Positions are mapped by aligning the UniProt sequence to each parsed chain, which is self-contained and testable offline. RCSB publishes a residue-level SIFTS mapping for every PDB entry; fetching it as a *second opinion* would turn a silent disagreement into a visible one. Only useful for `rcsb` imports — an upload and an AlphaFold model have no SIFTS record | A5 | A5 merged | 4h |
| **A5 follow-up — colour the 3D surface by hydrophobicity and charge.** `GET /functional-regions` already returns per-residue Kyte-Doolittle, formal charge and relative accessibility as per-chain arrays; the viewer renders none of them. Needs a Mol* colour theme driven from the store, beside the existing pLDDT/B-factor schemes | A5 | A5 merged | 4h |
| **A5 follow-up — a branched ligand is reported as its components.** `bound_ligands` emits one entry per HETATM residue, so 1HEW's tri-N-acetylchitotriose is three NAG rows sharing contact residues rather than one ligand. Grouping needs covalent connectivity (or the mmCIF branched-entity records, which the PDB format does not carry) | A5 | A5 merged | 3h |
| **A5 follow-up — a free amino acid bound as a substrate is skipped.** Ligand detection excludes any HETATM group carrying a complete N/CA/C backbone, which is what keeps selenomethionine inside a helix from being reported as a bound ligand. It also skips a genuine free-amino-acid ligand. Under-reporting rather than mis-marking is the right direction, but an entity-type check on mmCIF would fix it properly for RCSB imports | A5 | A5 merged | 2h |
| **The chain tree is `xl`-only.** Below 1280px the viewer drops the left rail entirely and only the stacked tab rail remains, so there is no chain navigation on a laptop in a split window. Needs a collapsible drawer or a sixth tab | follow-up | P10 | 2h |
| **Mol\*'s canvas renders on a near-white background inside an otherwise dark workspace.** Pre-existing and unrelated to P10, but it is the most visible remaining inconsistency in the viewer. The fix is a Mol\* renderer background parameter in `components/molstar-viewer.tsx` — deliberately not touched here because P8 owns that file | follow-up | P8 merged | 30m |
| Batch RCSB search enrichment via the GraphQL Data API (currently up to 50 REST calls per search) | follow-up | — | 2h |
| Virtualise the sequence panel (one `<button>` per residue gets heavy above ~2,000 residues) | follow-up | — | 2h |
| Make HETATM amino acids (e.g. MSE) selectable — currently skipped consistently by both parser and panel | follow-up | — | 1h |
| Re-record `uniprot_annotations_P01308.json` / `P00533.json` from a live UniProt response. They were hand-authored against the UniProtKB JSON schema because this environment's egress policy blocks `rest.uniprot.org` entirely; a live capture would also re-confirm the 28 field names | follow-up | egress to rest.uniprot.org | 30m |
| ~~Similar proteins / homologs via UniRef~~ — **done in P8** (`feature/p8-blast`): `find_uniref_cluster` / `fetch_uniref_members` on `UniProtClient`, `GET /api/proteins/{uid}/similar` | P8 | — | done |
| Paste-your-own-sequence BLAST entry point. `POST /api/blast` already accepts a raw `sequence` and all four programs; the Similarity panel only offers blastp on the stored structure's own sequence, so blastn / blastx / tblastn are reachable by API but not by UI | follow-up | P8 | 2h |
| Surface BLAST alignment text. `BlastHsp` deliberately drops `hsp_qseq`/`hsp_mseq`/`hsp_hseq` (~90% of the payload); an alignment view would need a per-hit detail fetch | follow-up | P8 | 3h |
| BLAST job registry is in-memory, so a backend restart makes every in-flight job unpollable even though EBI still has it. Same fix as the protein registry — belongs to the persistence slice | follow-up | P8 | — |
| CD-Search (conserved domains) — the slice design's "CDART, partly" row. NCBI has a documented URL API; not built in P8 | follow-up | — | 4h |
| Automated browser-level coverage for `extractResidueRecords` — manually verified 2026-08-21 on both a PDB upload and a 4-chain RCSB mmCIF, so this is now regression protection rather than an unknown | follow-up | a browser test runner | 3h |
| **P8 — Similarity & BLAST.** EBI NCBI BLAST REST (submit/poll/retrieve — the project's first async flow) + UniRef similar proteins | P8 | — | 1-2d |
| **P9 stretch — complex topology graph.** Not built in P9, and no longer speculative: `GET /intact/complex-ws/export/{CPX}` returns MI-JSON whose `participants[].features[]` carry `category: "bindingSites"` and a `linkedFeatures` array pairing one participant's binding region with another's. Those pairs are the real edges — the `/search` payload P9 uses has no pairwise data at all, so any graph drawn from it would be a hub-and-spoke picture asserting bindings the data never states. Needs: a second client method, an edge-list model, an SVG layout component, and the export payload is heavy (it embeds full sequences) | P9 | P9 merged | 1-2d |
| **P9 follow-up — link a complex to its experimental structures.** The same `/export/{CPX}` MI-JSON lists `wwpdb` and `emdb` cross-references for the complex (CPX-26675 carries 1IR3, 4XLV, 8U4B and more). In a structure viewer that is a direct "load the experimental structure of this complex" path into the existing RCSB import | P9 | P9 merged | 3h |
| **Superimpose the two structures in 3D on `/compare`.** P7 computes and reports the RMSD but does not overlay the coordinates — the panes stay independent. Needs the transform applied Mol\*-side (or a transformed copy served) and one shared canvas | follow-up | P7 | 4h |
| **Compare affordance on the search page.** P7 ships one from the viewer header. A "compare these two" selection on `/search` would import both hits and land on `/compare` in one step — the predicted-vs-experimental pair is one query away | follow-up | P7 | 2h |
| Export the comparison report (spec A3 asks for it; P7 ships the on-screen comparison only). Overlaps the deferred F9 export slice — decide there rather than adding a one-off | follow-up | P7 | — |
| Persistence slice — the in-memory registry resets on restart, so `/viewer/{id}` 404s afterwards though the file survives on disk | separate slice | Postgres decision | — |
| **A1 follow-up — warn when a *selected* region is low confidence.** Spec A1 asks for this explicitly and it is the one A1 requirement not shipped: the panel lists every low-confidence range, but nothing cross-references the current `selection-slice` selection against them. Needs a selector over `confidence.low_confidence_regions` and a line in the selection UI | A1 | A1 merged | 2h |
| **A1 follow-up — finer pLDDT histogram.** A1 ships the four-band distribution (which is what the low-confidence warnings are built on); spec A1 also says "pLDDT histogram", which usually means 10-point bins. The per-residue values are already extracted in `services/confidence.extract_plddt`, so this is a second projection, not new I/O | A1 | A1 merged | 1h |
| **A1 follow-up — no automated coverage of the PAE canvas painting loop.** jsdom returns `null` from `getContext("2d")`, so `pae-heatmap.tsx`'s `putImageData` loop is only covered by its own fallback branch. The colour function under it is fully tested; the loop was verified by screenshotting headless Chrome. Same gap, same cause, as the `extractResidueRecords` row above — one browser test runner would close both | A1 | a browser test runner | 2h |
| ~~A5 Binding-pocket / functional-region detection — UNPLANNED GAP~~ — **built**, see *Done* (`feature/a5-functional-regions`). Phase 1 only; pocket *prediction* remains deliberately unbuilt with a stated reason | spec gap | — | done |
| ~~A1: PAE heatmap and low-confidence-region warnings are in `spec.md` but in no deferral list~~ — **built**, see *Done* (`feature/a1-confidence`) | spec gap | — | done |
| Slice section 7 specifies `400 { error, suggestion }`; no `suggestion` field is implemented anywhere in the backend | spec drift | — | 45m |
| Slice section 6.1 specifies a content sniff (first line is `HEADER`/`data_`); only extension/size/empty checks exist | spec drift | — | 30m |
| Slice section 5.2 promises parser warnings for missing atoms, multiple models, and chain breaks; none are emitted (only non-standard residues / no chains) | spec drift | — | 1h |
| F3: `SelectionMode` / `setMode` exist in `selection-slice.ts` but no UI calls them — select-by-type / chain / range / property, and the left-sidebar filter panel from slice section 4.1, were never built | spec drift | — | 3h |
| Three files exceed AGENTS.md's 200-LOC cap: `app/viewer/[id]/page.tsx` (207), `components/molstar-viewer.tsx` (203), `lib/residue.ts` (202) | cleanup | — | 45m |
| Type drift: `ingest.parse_and_register`'s `source` Literal omits `"uniprot"`, which `import_.py` passes. Runtime-fine leftover from PR #11 | cleanup | — | 15m |
| Per-phase test counts in `docs/smoke-tests.md` (P2 "14 passed", P3 "31 passed", P5.5 "90/103") are stale against the current 127/133 | docs | — | 20m |

---

## Blocked

_No blocked tasks._

| Task | Blocked by | Notes |
|---|---|---|

---

## Done

| Task | Phase | Date | PR / commit |
|---|---|---|---|
| **A1 merged** -- PAE heatmap + low-confidence region warnings. Bands reproduce AlphaFold's published fractionPlddt* exactly | spec gap | 2026-08-24 | PR #21, `8077803` |
| **A5 merged** -- functional regions: curated sites mapped through a BLOSUM62 alignment, observed ligand pockets, surface profile | spec gap | 2026-08-24 | PR #22, `5d1b271` |
| **P6 merged** -- UniProt annotation panel (28 fields, `/annotations`, Annotations tab) | P6 | 2026-08-22 | PR #16, `d4d58c7` |
| **P7 merged** -- comparison view: `/compare`, two Mol* viewers, BLOSUM62 alignment, CA superposition RMSD | P7 | 2026-08-23 | PR #17, `b7e2a4e` |
| **P9 merged** -- Complex Portal viewer: participants + stoichiometry, over-match filtering surfaced | P9 | 2026-08-23 | PR #18, `15605f4` |
| **P10 merged** -- chain tree, honest landing page, and the `secondary_structure.available` donut fix | P10 | 2026-08-24 | PR #20, `a59fc5e` |
| **P8 merged** -- BLAST (blastp/blastn/tblastn/blastx) + UniRef homologs, Similarity tab. All four programs verified against the LIVE EBI service | P8 | 2026-08-24 | PR #19, `e06be37` |
| **P10: chain tree in the viewer's left rail** — per-chain label, residue count, share of the structure, residue-class composition bar, expandable per-class counts and ordinal-range chips. Drives the existing `setSelection`, so a chain or range click highlights in Mol\* and scrolls the sequence panel through the P4 path | P10 | 2026-08-24 | `bc36bd8` |
| **P10 BUGFIX: the analytics donut no longer reports "100% coil" for a structure that declares no secondary structure.** `SecondaryStructurePercentages.available` is now a required frontend field; an unannotated split renders as a single neutral "Not annotated" ring with an amber note, matching P7's comparison-table treatment | P10 | 2026-08-24 | `fef9cd7` |
| **A1 — AlphaFold confidence analysis.** `GET /api/proteins/{uid}/confidence`: pLDDT band table, every contiguous low-confidence run with residue ranges as readable warnings, and the PAE matrix binned to a declared resolution. Folded into the **Analytics** tab, so `RAIL_TABS` is untouched. Verified live against AlphaFold DB on P01308 (110x110 full-resolution PAE) and P0DTC2 (1,620,529 cells binned 10x to 128x128), plus 1CRN and a hand-uploaded model | A1 | 2026-08-24 | `feature/a1-confidence` |
| **P10: landing page made honest** — the `empty` badge and the never-built chain-tree promise are gone, the rail carries three real entry points, and the tab preview lists all five viewer panels. A test renders HomePage and ViewerRail together and fails if the two tab lists diverge | P10 | 2026-08-24 | `80e61ae` |
| **P10: density pass** — chain rows open by default on structures with few chains, landing centre column carries a "Wired to" strip naming the four integrated databases (cross-checked against `backend/app/services/*.py` by a test), plus the optional molecular backdrop as one opt-in CSS class kept off the viewer routes | P10 | 2026-08-24 | `82de2ec` |
| **P10: charts became testable at all** — jsdom has no `ResizeObserver`, so every Recharts component threw on render and no chart had ever been covered by a test. `vitest.setup.ts` now stubs it | P10 | 2026-08-24 | `fef9cd7` |
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
| Final whole-branch integration review — verified the P4/P5 residue seam is correct for mmCIF as well as PDB by emulating Mol\*'s mmCIF pipeline against BioPython on an adversarial structure | P5.5 | 2026-08-19 | review agent |
| **P5.5 CRITICAL**: pLDDT color inversion fixed — `PLDDT_COLOR_DOMAIN = [100, 0]` so confident regions read blue. `hasPlddt` is now a *required* param on `applyColoring`, making a silent regression a type error | P5.5 | 2026-08-19 | PR #3 |
| P5.5: organism read from raw mmCIF entity-source categories (was `None` on every RCSB import) | P5.5 | 2026-08-19 | PR #3 |
| P5.5: `has_plddt` surfaced in the UI — pLDDT coloring no longer offered on X-ray entries | P5.5 | 2026-08-19 | PR #3 |
| P5.5: `search-view.tsx` split under the 200 LOC limit; landing page + README stop denying shipped features | P5.5 | 2026-08-19 | PR #3 |
| P5.5: PDB/mmCIF parser-parity regression test pinning residue ordinals | P5.5 | 2026-08-19 | PR #2 |
| P5.5: AlphaFold fallback file URL derived from `latestVersion` instead of hard-coded v4 | P5.5 | 2026-08-19 | PR #1 |
| P5.5: storage `OSError` returns a generic 500 instead of leaking the storage path | P5.5 | 2026-08-19 | PR #6 |
| P5.5: upload/import ingest flow + constants deduped into `services/ingest.py` | P5.5 | 2026-08-19 | PR #9 |
| P5.5: UniProt imports keep their own `source` provenance (`"uniprot"` is now a real `ProteinSummary.source`) | P5.5 | 2026-08-19 | PR #11 |
| P5.5: viewer representation/coloring reset on route change | P5.5 | 2026-08-19 | PR #8 |
| P5.5: retry with backoff + per-host concurrency cap on outbound HTTP | P5.5 | 2026-08-19 | PR #15 |
| **Manual smoke tests executed** (Playwright + live servers): landing page, Mol\* WebGL render of 1CRN, upload -> viewer, tabbed rail, metrics 46/327/4736 Da | P5.5 | 2026-08-21 | this commit |
| Verified P4 click-sync in-browser: clicking A:23 highlights in 3D and boxes the correct `E`; `a:7` lowercase search resolves to `I`; `A:999` errors with "chain A has 46 residues" | P5.5 | 2026-08-21 | this commit |
| Verified P5 live search: 75 results for "insulin", 25 from each of RCSB / AlphaFold / UniProt, `failed_sources` empty — AlphaFold's UniProt-crossref strategy works against the real API | P5.5 | 2026-08-21 | this commit |
| **Verified the P4/P5 seam on real data**: imported 4INS (4-chain mmCIF) from live RCSB; chains A21/B30/C21/D30 match the API, ordinals restart per chain, and clicking B:25 boxes `F` and highlights in 3D | P5.5 | 2026-08-21 | this commit |
| Verified the CRITICAL pLDDT fix visually: imported AlphaFold P01308, confident helix renders BLUE and the disordered loop pink — correct AlphaFold convention. pLDDT option correctly absent on uploaded PDB, present here | P5.5 | 2026-08-21 | this commit |
| Verified mmCIF organism extraction on live data (4INS -> "Sus scrofa") and the AlphaFold 404 path (`Q0Q0Q0` -> source-specific 404) | P5.5 | 2026-08-21 | this commit |
| **Human-confirmed the 3 mouse-driven checks**: 3D->sequence click direction, cofactor click preserves selection while background clears it, and rotate/zoom. Completes both directions of the P4 click-sync | P5.5 | 2026-08-21 | user confirmation |
| Fixed the Mol\* duplicate-`createRoot` race (async plugin construction vs synchronous React cleanup); regression test pinned by mutation | P5.5 | 2026-08-21 | `b7990dd` |
| B-factor coloring restored as its own scheme, so experimental structures can be coloured by B-factor again while pLDDT keeps its reversed domain | P5.5 | 2026-08-21 | `d9e81af` |
| Multi-entity mmCIF now reports every distinct organism (case-insensitive dedupe, length-capped with an explicit "and N more" rather than silent truncation) | P5.5 | 2026-08-21 | `54cba2d` |
| One-click launcher (`start.cmd` + `scripts/launch.ps1`) serving a production build — no dev-tools bubble, self-healing setup | P5.5 | 2026-08-21 | this commit |
| Full spec-compliance audit against `spec.md` and the slice design (9 acceptance criteria + F1-F9 / A1-A6 / S1-S4 inventory + doc drift) | P5.5 | 2026-08-21 | audit agent |
| **Fixed: secondary structure was 100% coil for every mmCIF and AlphaFold structure.** SS was read from `HELIX`/`SHEET` text records, which mmCIF does not have; now also reads `_struct_conf` / `_struct_sheet_range`. Verified live: 4INS went from 100% coil to 54.9% helix / 5.9% sheet, crambin's PDB numbers byte-identical | P5.5 | 2026-08-21 | `c17ba8e` |
| Production build switched to webpack — the Turbopack bundle was broken for the Mol\* route and rendered a dead page | P5.5 | 2026-08-21 | `415d20b` |
| Doc/UI drift corrected: README `CORS_ORIGINS` (its absence broke setup), stale test counts, landing page promising an unbuilt chain tree, stale P1 badge | P5.5 | 2026-08-21 | `217fc40` |
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
| 2026-08-24 | A5 maps UniProt sequence positions onto structure residues by **globally aligning the UniProt sequence against each parsed chain** and reading the correspondence out of the alignment, expressed in the parser's residue ordinals | A UniProt position is not a residue number and the difference is invisible in 3D. UniProt P00698 numbers hen lysozyme's 18-residue signal peptide, so its curated active sites at 53 and 70 are Glu35 and Asp52 in every crystal structure; P04585 is a 1435-residue polyprotein whose protease active site at 513 is Asp25 of the mature enzyme. Reading the position as an index, or as an `auth_seq_id`, marks a plausible-looking wrong residue in both cases. Ordinals rather than `auth_seq_id` because that is the coordinate `parser.py` and `residue-index.ts` already share — the seam is untouched | yes, but the refusals must not be loosened |
| 2026-08-24 | A chain the alignment does not support is **refused**, with the reason published in `ChainMapping`: under 90% identity over comparable columns, under 50% identity coverage of the shorter sequence, fewer than 4 comparable columns, or an alignment over 16M cells | Same posture as P7's RMSD refusal. Both floors are load-bearing and neither covers for the other: a 55%-identity chain clears coverage and fails identity, a chain sharing one short terminus clears identity at 100% and fails coverage. Coverage is measured over the *shorter* sequence so a 99-residue mature protease still scores 100% against a 1435-residue polyprotein | yes |
| 2026-08-24 | **"Predicted pocket regions" (A5 bullet 3) is NOT delivered.** The only pockets reported are the residues observed within 4 A of a ligand present in the file; an apo structure is told plainly that there is nothing to show | Phase 2 is where an ML scorer belongs. A geometric cavity search shipped under the label "predicted pocket" in Phase 1 would be a heuristic wearing a prediction's clothes — the same failure as an RMSD from an unverified pairing. Cost: an apo structure gets curated sites, surface and charge but no pocket | yes — it is an addition, not a change |
| 2026-08-24 | `GET /functional-regions` **degrades on a UniProt outage instead of returning 502**, unlike `/annotations` and `/complexes` | Half this payload — bound ligands, contact residues, accessibility, hydropathy, charge — is measured from the coordinate file and does not depend on UniProt. Discarding a correct structural analysis to report someone else's outage is the wrong trade. The failure is stated in `notes` so a transient outage never reads as "this protein has no curated sites" | yes |
| 2026-08-24 | A5 is folded into the **Annotations tab** rather than given a seventh rail tab | Its first two bullets are four more UniProt positional feature types beside the ones that tab already renders, and the structure-observed half attaches to the same residues — the one genuinely valuable output is seeing that a curator and this file agree on a residue, which only reads if they sit side by side. The rail already carries six tabs at 24rem, which P10's log declined to grow for a measured reason. Cost: the Annotations tab is longer, and its no-accession case became a notice above real content rather than a dead end | yes |
| 2026-08-24 | Solvent accessibility is Shrake-Rupley over the **polymer alone**, waters and ligands stripped, normalised by Tien et al. (2013) maxima, and skipped above 30k atoms | Which surface is a choice, and leaving solvent in would bury exactly the pocket residues the rest of the module reports. The atom bound is measured (~0.1 ms/atom on this machine) and never truncates: hydropathy and charge come back in full with a note saying the accessibility arrays are absent | yes |
| 2026-08-24 | High-priority residues carry **reasons, not a score** | A score implies a model fitted to something, and nothing here was. The ordering is a count of how many independent kinds of evidence converge — curated, observed, or both — and `Site` / `DNA binding` regions are excluded from it because a 48- or 191-residue domain would bury the handful of residues the list exists to surface | yes |
| 2026-08-24 | A1 bins the PAE matrix to a **cell budget** (16,384 = 128x128), never to a residue cap | PAE is quadratic: 1,273 residues is 1,620,529 cells and a 9.4 MB upstream document. A residue cap would refuse or clip a large protein — the truncating-limit failure mode. A cell budget bins it instead and reports `bin_size`, `size`, `aggregation` and a prose `resolution_label` with the data, so a binned matrix always says it is binned. Every protein up to 128 residues is untouched | yes — one constant |
| 2026-08-24 | Binned cells are the **mean** over their block, not the maximum | The mean is the standard PAE reduction and preserves the domain-block structure a reader is looking for; a max would push every block toward the error ceiling and hide exactly the signal. The choice is stated in `aggregation` and in the label rather than left implicit | yes |
| 2026-08-24 | The PAE colour ramp follows **AlphaFold DB's own plot** — dark green = low error, pale = high error — even though pLDDT in this codebase runs bright = confident | PAE is an error and pLDDT is a confidence; they genuinely run in opposite directions, and making them *look* alike is the hazard, not the inconsistency. Matching the convention a reader knows from an AFDB entry page is worth more. The direction is pinned by a luminance-monotonicity test, and both ends of the legend are named in words and in Angstroms | yes — one ramp constant, one test |
| 2026-08-24 | Per-residue pLDDT is read from the **stored structure file's B-factor column**, not from AlphaFold's `fractionPlddt*` API fields | The API fields say how much of a model is disordered but never *where*, so they cannot produce residue ranges; and they only exist for entries we imported. Reading the file means a hand-uploaded AlphaFold model gets full band and region analysis with no accession at all. Cross-validated: the bands computed from AF-P01308-F1's B-factors reproduce AlphaFold's published fractions (0.509 / 0.364 / 0.127 / 0.0) exactly, and the mean reproduces `globalMetricValue` 52.91 | yes |
| 2026-08-24 | The PAE document URL comes from the prediction payload's `paeDocUrl`; no filename is ever guessed | AlphaFold moved both the version segment and, in 2025, the entry-id scheme — `P0DTC2` now answers as `AF-0000000365840314`, so the `AF-{accession}-F1-...` template 404s on exactly the large entries the size guard exists for. The existing `_fallback_pdb_url` guess is left alone; it is a documented fallback for a payload missing `pdbUrl`, which is a different case | no — the template is provably wrong |
| 2026-08-24 | `/confidence` has no 502: an AlphaFold outage degrades the `pae` block to `available: false` plus a reason, and leaves the pLDDT analysis intact | pLDDT comes from the file already on disk, so an upstream failure has no bearing on it. Failing the whole request would cost the user the analysis that was never at risk. Absence is always a stated reason, never a zeroed matrix — the precedent P10 set for the secondary-structure donut and P7 for the comparison warning | yes |
| 2026-08-24 | The binned PAE cache lives in `services/confidence.py` and stores the **binned** matrix, not the raw one | `cache.py`'s `TTLCache` bounds entries by count, which is only a real memory bound when entries have a fixed ceiling. A raw-matrix cache would hold up to 7.3M floats per entry; a binned one holds at most `MAX_PAE_CELLS`, so 32 entries is ~17 MB whatever the proteins' sizes. Keyed by `accession:max_cells` so two budgets never share a slot | yes |
| 2026-08-24 | Low-confidence regions are reported unfiltered and uncapped — no minimum run length, no maximum region count | A minimum length would hide real single-residue dips; a cap would silently truncate exactly the disordered proteins the analysis exists for. The worst case is bounded anyway (~1,350 regions at AlphaFold's 2,700-residue fragment limit). Live, P0DTC2 produced 43 regions and all 43 render | yes |
| 2026-08-24 | A1 folds into the **Analytics** tab rather than adding a rail tab | Confidence is analytics about the model, and `app/__tests__/landing-rail-preview.test.tsx` asserts the landing page advertises exactly the tabs the rail renders — a new tab means editing `RAIL_TABS` in a file A5 may also be touching. Cost: `analytics-panel.tsx` grows one `<Section>` and one import | yes |
| 2026-08-24 | Band edges (`min_plddt` / `max_plddt`) travel on the wire and the UI never re-declares 70 | A duplicated threshold that drifts gives a legend describing the wrong measurement while every count stays correct — invisible to any test that only checks counts. A mutation swapping the advertised edges survived the first sweep for exactly that reason | yes |
| 2026-08-24 | An unannotated secondary-structure split renders as one neutral "Not annotated" ring carrying no percentage, rather than the backend's `helix 0 / sheet 0 / coil 1` placeholder plus a warning | P7's table keeps its numbers and adds the warning, which works because a delta table reads as data either way. A donut is different: its legend would still say "Coil (100%)", which is the exact false claim the flag exists to prevent, and a reader who skips the note takes the ring at face value. The warning is kept, worded as P7 words it | yes |
| 2026-08-24 | `SecondaryStructurePercentages.available` is REQUIRED in the frontend type, though the backend still defaults it to `true` | The field has always been on the wire; making it optional in TypeScript is exactly how the donut came to ignore it for two phases. Required means a future consumer that drops it fails to compile instead of silently reporting a placeholder as a measurement. No wire-format change — the backend default is untouched | yes |
| 2026-08-24 | The chain tree drives `selection-slice`'s existing `setSelection` and adds no state of its own | A second selection path would have to be kept in sync with the Mol\* click handler, the sequence panel and the `A:12` finder, and the P4 seam is the load-bearing part of this codebase. Because the rail both writes and reads the one store, a 3D click shows up as the rail's per-chain "N sel" count for free — which is also how the wiring was verified in the browser | yes |
| 2026-08-24 | `chainSegments` grows the segment size to stay inside a chip budget; it never caps the number of residues covered | A fixed chip count would silently stop partway through a long chain and hide its tail — the failure mode a truncating limit always has. The union of the segments is always exactly `1..residueCount`, pinned by a test across eight chain lengths | yes |
| 2026-08-24 | Chain rows start expanded at four chains or fewer | Presentation default only, for the rail this phase exists to un-empty: a monomer showed one short row and nothing else. Nothing is hidden at any chain count — every chain is always listed, and the chevron overrides the default either way | yes |
| 2026-08-24 | The molecular backdrop is one opt-in CSS class applied to the landing page's centre column only | The client ranked the texture last, and the Mol\* canvas is the thing most easily spoiled by a background. Scoping it to a class the viewer routes never apply makes "can this affect the 3D view" answerable by grep rather than by judgement | yes — delete the class |
| 2026-08-24 | `viewer-rail.tsx` was left untouched despite P10 owning "the rail should not feel cramped" | Five tabs measured fine at the 24rem rail width in Chrome, so there was nothing to fix — and P8 is editing that exact file to add a Similarity tab. Editing it for no measured benefit would have bought a merge conflict and returned nothing | yes |
| 2026-08-23 | P9 uses `/search/{accession}` alone; `/details/` and `/complex-simplified/` are not called | Verified against the live service, and the brief's assumed contract was wrong: `/details/` is keyed by IntAct `EBI-*` accessions, not `CPX-*` ones (`/details/CPX-2158` is a 404; the service's own docs example is `/details/EBI-1163476`). `/complex-simplified/{CPX}` returns byte-for-byte the element shape `/search` already delivered. Each `/search` element already embeds the full interactor list with stoichiometry, so the participant table costs one request rather than one per complex | yes |
| 2026-08-23 | A complex is listed only when the protein is an actual participant; the raw upstream count is kept in `search_matches` | Complex Portal's search is full text and over-matches. `search/P01308` returns nine records, two of which — the insulin *receptor* complexes — only name "Insulin (P01308)" in their curated description and contain no insulin. Listing those as complexes containing insulin is wrong biology. Filtering silently would hide the over-match, so the upstream total is reported and the panel accounts for the difference | yes |
| 2026-08-23 | Accessions are reduced to their base form before querying, and participants are matched at base level | Complex Portal indexes base accessions only: `search/P01308-1` returns zero where `search/P01308` returns nine, so an isoform import would look complex-less. The same reduction on the participant side is load-bearing in the other direction — in CPX-16536, the one curated complex INSR belongs to, P06213 appears only as the mature chains `P06213-PRO_0000016687/9`, so a plain string comparison drops it | yes |
| 2026-08-23 | Curated complexes sort ahead of predicted ones | Complex Portal ranks by Solr relevance and guarantees nothing about where predicted complexes land. Insulin is the case that forces the issue: every complex actually containing P01308 is predicted and carries no function text at all. The panel must not open on a prediction while a curated complex with a real function sits further down the pulldown, and must label predicted ones rather than passing an inference off as curated knowledge | yes |
| 2026-08-23 | Upstream participant links are scheme-checked and upgraded to https rather than passed through | Complex Portal ships its ChEBI links as plain `http://`. These strings land in an `<a href>`, so anything that is not http(s) is dropped rather than rendered — a `javascript:` URL arriving from a third-party feed is an XSS vector, not a link | yes |
| 2026-08-23 | P9 fixtures are recorded responses, never hand-authored | Production `complex-ws` was returning 503 when the work started, so the five fixtures were first captured from EBI's dev deployment; when production recovered mid-build all five were re-captured from `www.ebi.ac.uk` and compared — **semantically identical, so the shipped fixtures are production responses**. Recording rather than hand-writing is what earned the phase its two load-bearing findings: a hand-written fixture would have encoded the brief's wrong assumption about `/details/` and could never have surfaced the free-text over-match | n/a |
| 2026-08-22 | P7 aligns with BLOSUM62 + affine gaps (−11/−1) rather than a flat match/mismatch `globalms` | The brief said "globalms-style", which is the right *shape* — global, affine gaps — but flat match/mismatch scoring makes "percent similarity" meaningless: with no substitution matrix there is no notion of a conservative substitution, so similarity would just restate identity. BLOSUM62 is what blastp and EMBOSS use for proteins and gives the '+' column a definition. Same affine gap model either way | yes — one function builds the aligner |
| 2026-08-22 | End gaps are FREE in the P7 alignment (EMBOSS `needle`'s default) | A3's headline case is an AlphaFold model covering a whole UniProt sequence against a crystal form covering a construct. Charging for that overhang pushes the aligner into shredding the matching core to shorten it, which is both a worse alignment and a worse residue pairing for the RMSD. Cost: `identity_percent` over the full alignment length reads low, which is why `identity_percent_aligned` is reported beside it | yes |
| 2026-08-22 | P7 reports three identity denominators, not one | Identity-over-alignment-length and identity-over-overlap are both standard, differ by a lot on a fragment-vs-full-length pair, and are routinely confused. Publishing one and calling it "identity" would be picking a side silently. Cost: four stat tiles instead of three | yes |
| 2026-08-22 | `X` never counts as an identity or a similarity, including `X` against `X` | `X` is the parser's placeholder for a non-standard residue. Counting two placeholders as a match inflates identity exactly for the heavily-modified structures where it is least justified | yes |
| 2026-08-22 | RMSD is REFUSED, not approximated, when the residue pairing cannot be verified — fewer than 3 CA pairs, or a residue list that disagrees with the parsed sequence | A wrong RMSD is worse than no RMSD: it is confident, precise, and unfalsifiable by eye. The length check is the guard against `services/compare.py` and `parser.py` ever disagreeing about which residues are polymer, which would misalign every pair after the divergence | yes — but the refusals should not be loosened |
| 2026-08-22 | A twilight-zone (<20%) identity is FLAGGED, not refused | A3 explicitly lists "similar folds with low sequence identity" as a use case, so refusing there would decline the feature's own use case. The caveat travels with the number and renders as prominently as it does | yes — one threshold |
| 2026-08-22 | `/compare`'s representation/coloring select offers only schemes truthful for BOTH structures | `plddt` and `bfactor` read the same column and which is honest depends on `has_plddt`. When the pair disagrees — predicted vs experimental, the case the page exists for — one shared select cannot label it for both, so both drop out. Chosen over per-pane selects, because two panes rendered differently compare the rendering rather than the structures | yes |
| 2026-08-22 | P7 reports RMSD numerically but does not overlay the two structures in 3D | The fit is computed and never applied: `Superimposer.apply()` is not called, so neither input is mutated. A real 3D overlay needs the transform pushed through Mol\* onto one shared canvas, which is its own piece of work — filed as a follow-up. Reporting the number is what spec A3 asks for ("compute RMSD where alignment is possible") | yes |
| 2026-08-22 | `compute_analytics` / `parse_structure_for_analytics` made public in `api/proteins.py` rather than duplicated for compare | The comparison needs the same analytics for two proteins at once. A second parse path is a second place for format detection and SS reading to drift — the same reasoning that extracted `services/ingest.py` in P5.5. Cost: one api module imports another | yes — extract to `services/` if a third caller appears |
| 2026-08-22 | UniProt return-field names verified against UniProt's own `result-fields` column enum (`ebi-uniprot/uniprot-website`, `src/uniprotkb/types/columnTypes.ts`), not the help page | `rest.uniprot.org` and `www.uniprot.org` are both blocked by this environment's egress policy, so neither the REST config endpoint nor the help page was reachable. The website repo's enum documents itself as mirroring `/api/configure/uniprotkb/result-fields` and is UniProt's own source — a better authority than the brief. Cost: it can lag a UniProt release; a 400 from the entry endpoint is the symptom | yes — re-verify against the live endpoint when egress allows |
| 2026-08-22 | `xref_uniref` dropped from the P6 field set | It is not a UniProtKB return field. UniRef is a separate dataset with its own endpoint; asking for it makes the whole entry request a 400 and takes every other section down with it. "Similar proteins" therefore belongs to P8, where UniRef gets its own client | no — the field does not exist |
| 2026-08-22 | `xref_ndex` included even though the slice design filed NDEx under "needs another source" | It exists as a UniProtKB cross-reference field, so the client's NDEx ask is answered for free inside the call we were already making. A dedicated NDEx client is still the route to network *contents* | yes |
| 2026-08-23 | BLAST is asynchronous end to end: `POST /api/blast` returns a job id and never waits; the browser polls `GET /api/blast/{job_id}` | A BLAST search takes 30 s to several minutes. A synchronous endpoint would be held open past every proxy and load-balancer timeout in the path, and would lose the results when one fired. This is the first place the project's uniform request/response shape genuinely does not fit | no — the upstream service is asynchronous |
| 2026-08-23 | Polling *policy* lives in `services/blast_jobs.py`, separate from the transport in `services/blast.py` | Three behaviours only make sense as policy: a terminal status is answered from memory with zero upstream calls, upstream polls are throttled to at most one per 2 s however fast the browser asks, and the result is downloaded exactly once. Putting them in the client would make "one method, one round trip" untrue and make the transport untestable in isolation | yes |
| 2026-08-23 | The API model drops BLAST's aligned sequence strings (`hsp_qseq` / `hsp_mseq` / `hsp_hseq`) and keeps only coordinates | They are ~90% of the payload by size — the recorded 50-hit response is 348 kB, mostly alignment text — and the results table does not render them. Keeping them would also make the in-memory job cache's size bound a guess rather than a real one | yes — add them back with a per-hit detail endpoint if the alignment view is ever built |
| 2026-08-23 | A hit's headline identity / E-value / score come from its **best HSP chosen by score**, not `hit_hsps[0]` | EBI orders HSPs by score today, but a table that silently reported a weaker alignment if that ever changed would be almost impossible to notice from the outside. Pinned by a test that reverses the HSP order and asserts the summary does not move | no reason to |
| 2026-08-23 | UniRef lookup is a membership **search** (`uniref/search?query=uniprot_id:{acc}`), not a direct `GET uniref/UniRef50_{acc}` | A protein is only named after its cluster when it happens to be the cluster's representative sequence. The direct URL 404s for every other member — which is most proteins | no |
| 2026-08-23 | `GET /api/proteins/{uid}/similar` excludes the query protein from `members`, and skips UniParc members | A list of "similar proteins" whose first row is the protein you are looking at is noise. UniParc records carry no UniProt accession at all (5 of the 25 in the recorded insulin cluster), so there is nothing to link to and nothing to import. `member_count` still reports the cluster's own total so the UI can say how many are being shown | yes |
| 2026-08-23 | EBI's required contact address is `BLAST_CONTACT_EMAIL`, defaulting to a non-personal GitHub noreply address with a warning logged on every use | EBI needs a way to reach the operator of a misbehaving client, and is entitled to block one they cannot contact. Defaulting to the maintainer's own mailbox would send a personal address to a third party as a side effect of running the app | yes |
| 2026-08-23 | The browser remembers a running job id in `localStorage`, keyed by protein | A multi-minute wait is long enough for the user to navigate away or reload. The server holds the job; the browser only needs the id. Without this, coming back would either lose the search or queue a duplicate at EBI | yes |
| 2026-08-22 | Annotations get their own `TTLCache`, separate from the metadata cache | The payloads are whole UniProtKB entries, an order of magnitude larger than a normalised metadata dict. One shared LRU 256 would let a single annotation lookup evict several search enrichments | yes |
| 2026-08-22 | A protein with no resolvable UniProt accession returns 200 with an empty payload and `accession_resolved: false`, not an error | A plain upload legitimately has no UniProt counterpart. That is not a failure the user can act on, and a 404/500 would make the panel show a red error where the honest answer is "there is nothing to show, here is why". Upstream *outages* during resolution degrade the same way; only a reachability failure on a known accession is a 502 | yes |
| 2026-08-22 | Annotation sections render expanded by default | The phase exists to answer "the interface looks a bit empty". A rail of ten collapsed headings reads emptier than nine. Collapsing is for getting a long section out of the way | yes — one default |
| 2026-08-22 | Cross-reference URLs are resolved on the backend; GO / Rhea / EC / OMIM links are built on the frontend | The backend already decides which databases become cross-references, so it owns their templates. The identifiers that arrive as bare strings inside other sections have no such gate, so their templates live beside the components that render them. Both sides return null rather than a dead link for malformed input | yes |
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
| 2026-08-21 | Ship a `start.cmd` / `scripts/launch.ps1` launcher that serves a **production** build | One double-click runs the whole app. Production rather than `next dev` specifically because the dev server paints a floating dev-tools bubble over every page, which has no place in a demo or submission | yes |
| 2026-08-21 | Launcher is idempotent and self-healing (creates venv, installs npm, builds only when missing) | A grader or new contributor should not have to read setup docs to run the thing; later runs still start in seconds | yes |
| 2026-08-21 | `organism` stays a single string even for multi-entity mmCIF, joined when entities genuinely differ | Changing `ProteinSummary`'s shape on the final day would break the frontend with no time to coordinate; truthfulness is achievable without a schema change | yes — a future assembly view wants a per-entity list |
| 2026-08-21 | B-factor gets its own coloring scheme rather than sharing the pLDDT toolbar entry | Gating the single entry on `has_plddt` silently removed B-factor coloring for every experimental structure. Two schemes over one shared entry, since they need opposite color domains | yes |
| 2026-08-21 | Read mmCIF secondary structure inside `services/analytics.py`, accepting the file I/O there | AGENTS.md says analytics is pure, but `_parse_ss_records_from_pdb` already read the file; adding a second I/O site beside it on ship day was lower risk than restructuring the module. Revisit if analytics grows | yes |
| 2026-08-21 | `SecondaryStructurePercentages.available` added as an optional field defaulting to `True` | Lets the API state "this file declares no SS" without changing the response shape the frozen frontend consumes. Chosen over a `warnings` entry because warnings live on `ProteinSummary` at parse time, while SS is determined at analytics time | yes |
| 2026-08-21 | Production build uses webpack (`next build --webpack`), not Turbopack | The Turbopack production bundle throws "module factory is not available" on the Mol\* route and renders a dead page. Dev is unaffected, so it only appears in the built app. `build:turbopack` kept for re-checking upstream | yes — revert when upstream is fixed |
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

### P6 — Annotation panel

Goal: open a protein and read real biological annotation beside the structure.

- [x] `ANNOTATION_FIELD_NAMES` — 28 verified UniProtKB return fields (was 7)
- [x] `UniProtClient.fetch_annotations` with its own TTL cache
- [x] `UniProtClient.find_accession_for_pdb` (the `xref:pdb-` fallback)
- [x] `uniprot_accession` on the RCSB polymer-entity metadata
- [x] `models/annotations.py` — `ProteinAnnotations` and its ten sub-models
- [x] `services/annotations.py` — pure projection + accession resolution
- [x] `GET /api/proteins/{uid}/annotations`
- [x] `AnnotationsPanel` + Annotations tab in the viewer rail
- [x] Backend pytest: 31 tests against hand-recorded fixtures
- [x] Frontend vitest: 22 tests (panel, links, store slice)
- [x] P6 smoke test in `docs/smoke-tests.md`
- [ ] Manual smoke test executed in a browser (needs a human)

### P7 — Comparison view (spec A3)

Goal: open two structures side by side and get a real answer to "how do these differ?"

- [x] `models/compare.py` — `CompareRequest` / `CompareResponse` and their eight sub-models
- [x] `services/compare.py` — pure alignment, diff, and superposition; no I/O
- [x] `POST /api/compare` in `api/compare.py`, three independent response layers
- [x] Global BLOSUM62 alignment with affine gaps and free end gaps (`Bio.Align.PairwiseAligner`)
- [x] Identity / similarity / alignment length, plus identity over the overlap
- [x] Superposition RMSD via `Bio.PDB.Superimposer`, residues paired through the alignment
- [x] `polymer_residues` pinned against `parser.parse` on the adversarial parity fixture
- [x] `/compare?a=&b=` route, two Mol\* viewers reusing `MolstarViewer` unchanged
- [x] Metric / chain-length / secondary-structure / composition diff tables
- [x] Alignment rendered in numbered 60-column blocks with a `|`/`+` match line
- [x] Compare button in the viewer header
- [x] Backend pytest: 34 tests, including five committed superposition fixtures
- [x] Frontend vitest: 24 tests, including the two-instance Mol\* lifecycle
- [x] P7 smoke test in `docs/smoke-tests.md`
- [ ] Manual smoke test executed in a browser (needs a human)
- [ ] 3D overlay of the superposed structures (filed as a follow-up)

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
- ~~Comparative protein view (A3)~~ — **built in P7**, 2026-08-22
- Similarity search (A4) — separate slice
- Contact map (A6) — separate slice
- Export system (F9: PDF / PNG / JSON / CSV) — separate slice
- User accounts + Postgres + projects — separate slice
- DSSP integration — separate slice (when we go beyond P3)
- Docker / CI / deployment — separate slice
- Stretch features S1–S4 (MD viewer, energy minimization, docking, async folding) — post-MVP
