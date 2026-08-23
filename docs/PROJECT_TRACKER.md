# Project Tracker

**Project:** AI-Powered Protein Structure Visualization Platform
**Living document.** Read before claiming work. Update on claim, on PR open, on merge.

**Last updated:** 2026-08-23 by Shubhodeep Chatterjee (P9 complex viewer claimed on `feature/p9-complexes`: Complex Portal client, `GET /api/proteins/{id}/complexes`, Complexes tab. P7 merged.)

---

## Current phase

**P6 and P7 in review, P8–P10 scheduled** — new client scope (annotations, comparison, BLAST, complexes) designed at [2026-08-22-annotation-comparison-slice-design.md](superpowers/specs/2026-08-22-annotation-comparison-slice-design.md) and dispatched to cloud agents.

_Previously:_ **Slice complete and verified (P0–P5).** All six phases merged, and the manual smoke tests have now been executed end-to-end in a real Chromium against live servers and live public APIs. Every acceptance criterion in spec section 12 that needs a browser has been demonstrated. Remaining items are enhancements, not gaps.

Active design: [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](superpowers/specs/2026-05-23-protein-mvp-slice-design.md)

---

## In progress

| Task | Owner | Branch | Status | Notes |
|---|---|---|---|---|
| **P6 — Annotation panel.** Enriched UniProt field set, `GET /api/proteins/{id}/annotations`, Annotations tab | shubhodeep | `feature/p6-annotations` | merged | Backend + tab both shipped. 166 backend / 155 frontend tests green, lint + webpack build clean. 43 mutations applied, all caught. Manual smoke test (docs/smoke-tests.md P6) still needs a human with a browser |
| **P7 — Comparison view (spec A3).** `/compare?a=&b=`, two Mol\* viewers, metric/composition/SS diff table, `POST /api/compare` pairwise alignment, superposition RMSD | shubhodeep | `feature/p7-comparison` | PR open | All four deliverables shipped, RMSD included. 200 backend / 213 frontend tests green, lint + webpack build clean. 53 mutations applied, all caught. Branched from `main` at `d4d58c7`; touches no P6 file and does NOT touch the residue-ordinal seam. Manual smoke test (docs/smoke-tests.md P7) still needs a human with a browser |
| **P9 — Complex viewer.** EBI Complex Portal client, `GET /api/proteins/{id}/complexes`, Complexes tab with participant + stoichiometry table | shubhodeep | `feature/p9-complexes` | PR open | Data tier shipped: 207 backend / 178 frontend green, lint + webpack build clean, 65 mutations applied and all 65 caught. **Topology graph deliberately NOT shipped** — see the follow-up row and the decisions log. Fixtures are real recorded responses. Manual smoke test (docs/smoke-tests.md P9) still needs a human with a browser |

---

## Ready to claim

Follow-ups discovered during P4/P5. None block the slice; each was deliberately deferred with a reason.

| Task | Phase | Dependencies | Estimate |
|---|---|---|---|
| Batch RCSB search enrichment via the GraphQL Data API (currently up to 50 REST calls per search) | follow-up | — | 2h |
| Virtualise the sequence panel (one `<button>` per residue gets heavy above ~2,000 residues) | follow-up | — | 2h |
| Make HETATM amino acids (e.g. MSE) selectable — currently skipped consistently by both parser and panel | follow-up | — | 1h |
| Re-record `uniprot_annotations_P01308.json` / `P00533.json` from a live UniProt response. They were hand-authored against the UniProtKB JSON schema because this environment's egress policy blocks `rest.uniprot.org` entirely; a live capture would also re-confirm the 28 field names | follow-up | egress to rest.uniprot.org | 30m |
| Similar proteins / homologs via UniRef — dropped from P6 because `xref_uniref` is not a UniProtKB return field. Needs its own client against `rest.uniprot.org/uniref` | P8 | — | 3h |
| Automated browser-level coverage for `extractResidueRecords` — manually verified 2026-08-21 on both a PDB upload and a 4-chain RCSB mmCIF, so this is now regression protection rather than an unknown | follow-up | a browser test runner | 3h |
| **P8 — Similarity & BLAST.** EBI NCBI BLAST REST (submit/poll/retrieve — the project's first async flow) + UniRef similar proteins | P8 | — | 1-2d |
| **P9 stretch — complex topology graph.** Not built in P9, and no longer speculative: `GET /intact/complex-ws/export/{CPX}` returns MI-JSON whose `participants[].features[]` carry `category: "bindingSites"` and a `linkedFeatures` array pairing one participant's binding region with another's. Those pairs are the real edges — the `/search` payload P9 uses has no pairwise data at all, so any graph drawn from it would be a hub-and-spoke picture asserting bindings the data never states. Needs: a second client method, an edge-list model, an SVG layout component, and the export payload is heavy (it embeds full sequences) | P9 | P9 merged | 1-2d |
| **P9 follow-up — link a complex to its experimental structures.** The same `/export/{CPX}` MI-JSON lists `wwpdb` and `emdb` cross-references for the complex (CPX-26675 carries 1IR3, 4XLV, 8U4B and more). In a structure viewer that is a direct "load the experimental structure of this complex" path into the existing RCSB import | P9 | P9 merged | 3h |
| **P10 — Interface density + theme.** Populate the left rail (the chain tree promised on the landing page), denser professional layout, optional molecular background. Client ranked this BELOW functionality | P10 | P6 | 1-2d |
| **Superimpose the two structures in 3D on `/compare`.** P7 computes and reports the RMSD but does not overlay the coordinates — the panes stay independent. Needs the transform applied Mol\*-side (or a transformed copy served) and one shared canvas | follow-up | P7 | 4h |
| **Compare affordance on the search page.** P7 ships one from the viewer header. A "compare these two" selection on `/search` would import both hits and land on `/compare` in one step — the predicted-vs-experimental pair is one query away | follow-up | P7 | 2h |
| Export the comparison report (spec A3 asks for it; P7 ships the on-screen comparison only). Overlaps the deferred F9 export slice — decide there rather than adding a one-off | follow-up | P7 | — |
| Persistence slice — the in-memory registry resets on restart, so `/viewer/{id}` 404s afterwards though the file survives on disk | separate slice | Postgres decision | — |
| Surface `secondary_structure.available === false` in the UI. The API now says honestly when a file carries no SS assignment (e.g. AlphaFold models), but the donut still draws a full coil ring — the frontend ignores the flag | follow-up | — | 30m |
| **A5 Binding-pocket / functional-region detection — UNPLANNED GAP.** A spec-compliance audit found this is the only feature promised in `spec.md` that is neither built nor listed in any out-of-scope note. Every other unbuilt feature is a deliberate deferral. Decide explicitly: defer it or build it. | spec gap | — | — |
| A1: PAE heatmap and low-confidence-region warnings are in `spec.md` but in no deferral list (pLDDT coloring + mean-pLDDT are built) | spec gap | — | — |
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
