# Slice Design — Annotation, Comparison, Similarity & Complexes (P6–P10)

**Date:** 2026-08-22
**Source:** client feedback, 2026-08-22
**Predecessor:** [2026-05-23-protein-mvp-slice-design.md](2026-05-23-protein-mvp-slice-design.md) (P0–P5, complete)
**Status:** Approved for execution — scheduled to cloud agents
**Owner:** Shubhodeep Chatterjee (@shubhodeepcx)

---

## 1. What the client asked for

> "The interface needs to be a bit detailed as it looks a bit empty… check if it will be able to show
> the functions, catalytic activity (reaction, atom map), gene ontology and aspects, keywords…
> enzyme and pathway databases with BioCyc NDEx Reactome SIGNOR, protein names, gene names,
> encoded in which component, and organism name, proteomes and components, its subcellular location
> in cell map or diagram, features for transmembrane, involvement in disease, PTM/Processing,
> complex viewer…, similar proteins and homologs. Also tell me if BLAST is achievable."

Stated priority: **functionality over looks.** This design follows that ordering.

---

## 2. The central finding

**Roughly two-thirds of that list is one enriched UniProt call away.**

`backend/app/services/uniprot.py` currently requests **7 fields**:

```
accession,id,protein_name,organism_name,length,xref_alphafolddb,cc_function
```

UniProtKB exposes **over 100**. Everything below is already in the entry we are
fetching and discarding — no new vendor, no new auth, no new rate-limit budget:

| Client ask | UniProt field(s) | Status |
|---|---|---|
| Protein names, gene names | `protein_name`, `gene_names`, `gene_primary` | one field away |
| Organism name | `organism_name`, `organism_id`, `lineage` | partly built |
| Function | `cc_function` | **built** (search cards only) |
| Catalytic activity + reaction | `cc_catalytic_activity` (carries Rhea IDs + EC) | one field away |
| Gene Ontology + aspects | `go_p`, `go_c`, `go_f`, `go_id` — aspects are literally the three fields | one field away |
| Keywords (molecular function, biological process, ligand) | `keyword`, `keywordid` — KW categories map to the client's grouping | one field away |
| Subcellular location | `cc_subcellular_location` | one field away |
| Transmembrane features | `ft_transmem`, `ft_intramem`, `ft_topo_dom` | one field away |
| Involvement in disease | `cc_disease`, `ft_variant` | one field away |
| PTM / Processing | `cc_ptm`, `ft_mod_res`, `ft_carbohyd`, `ft_lipid`, `ft_signal`, `ft_chain`, `ft_peptide`, `ft_propep`, `ft_disulfid`, `ft_crosslnk` | one field away |
| Proteomes & components | `xref_proteomes` | one field away |
| Encoded in which component | `cc_subcellular_location` + `organelle` | one field away |
| Reactome / BioCyc / SIGNOR | `xref_reactome`, `xref_biocyc`, `xref_signor` | one field away |
| Similar proteins / homologs | `xref_uniref`, plus the UniRef REST API | mostly one field away |

**Not in UniProt, needs another source:**

| Client ask | Source | Difficulty |
|---|---|---|
| NDEx networks | NDEx REST (`public.ndexbio.org/v2/search/network`) | small — search by gene/UniProt id |
| Complex viewer (topology, stoichiometry, binding domains) | EBI **Complex Portal** REST (`www.ebi.ac.uk/intact/complex-ws`) | medium — data is easy, the interactive topology view is the work |
| Atom-level reaction map | **Rhea** REST, reached via the Rhea IDs inside `cc_catalytic_activity` | medium — Rhea gives ChEBI participants + reaction; a true atom–atom mapping is a specialist rendering problem |
| BLAST / homology search | see §4 | medium |

---

## 3. Phase plan

Ordered by value-per-effort, functionality first. Each phase is independently shippable.

| Phase | Deliverable | Why this order |
|---|---|---|
| **P6 — Annotation panel** | Enrich the UniProt client to the full field set; new `GET /api/proteins/{id}/annotations`; an **Annotations** tab with collapsible sections: Names & Origin, Function, Catalytic Activity, GO (3 aspects), Keywords, Subcellular Location, Transmembrane, Disease, PTM/Processing, Cross-references (Reactome/BioCyc/SIGNOR/NDEx/proteomes) | Single largest payoff. Answers ~9 of 13 asks from one already-integrated source, and fills the "empty interface" complaint with real content rather than decoration |
| **P7 — Comparison view (spec A3)** | `/compare?a={id}&b={id}`, two synchronised Mol\* viewers, side-by-side metric/composition/SS diff table, sequence alignment (Biopython `PairwiseAligner`) with identity %, optional superposition + RMSD | Explicitly requested. Also the client's "predicted vs experimental" use case, which our RCSB+AlphaFold search already sets up in one query |
| **P8 — Similarity & BLAST** | `POST /api/blast` against **EBI's NCBI BLAST REST** (job submit / poll / retrieve), plus UniRef-based "similar proteins"; results table linking back into import | Answers the BLAST question concretely and delivers homologs |
| **P9 — Complex viewer** | Complex Portal lookup by UniProt accession; participant + stoichiometry table; pulldown when a protein is in several complexes; topology graph if P6–P8 land comfortably | Highest effort, most specialist. Data tier is cheap; the interactive viewer is not |
| **P10 — Interface density & theme** | Denser professional layout, populated left rail (the chain tree that was promised and never built), optional subtle molecular/DNA background | Client ranked looks below functionality. Also, P6 alone removes most of the emptiness |

---

## 4. BLAST feasibility — direct answer

**Yes for the ones that matter; no for three, and it is worth knowing which.**

Do **not** drive `blast.ncbi.nlm.nih.gov/Blast.cgi` directly: it is rate-limited, discourages
programmatic use, and returns HTML-ish payloads. Prefer **EBI's NCBI BLAST REST service**
(`www.ebi.ac.uk/Tools/services/rest/ncbiblast`) — a clean submit → poll → retrieve contract,
documented for programmatic use, same underlying NCBI algorithms.

| Variant | Achievable | Route / obstacle |
|---|---|---|
| **protein BLAST (blastp)** | **Yes** | EBI REST, or UniProt's own BLAST. The natural default — we already hold the sequence |
| **nucleotide BLAST (blastn)** | Yes | EBI REST. We hold protein sequences, so needs a user-supplied nucleotide input |
| **tblastn** | Yes | EBI REST — protein query against translated nucleotide DB. Good fit |
| **blastx** | Yes | EBI REST — nucleotide query, needs user input |
| **CDART** (domain architecture) | Partly | No CDART API, but NCBI **CD-Search** has a documented URL API giving conserved domains — most of the value |
| **Global Align** (Needleman–Wunsch) | **Yes, locally** | Biopython `PairwiseAligner` — no network at all. Already a P7 dependency |
| **smartBLAST** | **No** | Web-only. No public API. Approximate with blastp restricted to model organisms |
| **IgBLAST** | **No** (hosted) | No public URL API. Only as a locally installed binary + germline DBs — a deployment project of its own |

**Caveats to design around:** BLAST jobs take **30 s to several minutes**. The synchronous
request/response shape used everywhere else in this codebase does not fit. P8 needs a
submit → poll → retrieve flow with a job id, and UI that tolerates a long wait. This is the first
genuinely asynchronous feature in the project.

---

## 5. Constraints carried forward

- **Everything stays offline-testable.** External HTTP mocked with `respx`/`pytest-httpx`; tests never hit a live API. Non-negotiable — it is what has kept the suite trustworthy.
- **The residue-ordinal seam is load-bearing.** `parser.py` and `frontend/lib/molstar/residue-index.ts` must agree, or every residue click targets the wrong residue. Any change touching residues changes both sides together, with a test pinning the agreement.
- **Production builds use webpack.** `next build --webpack`; the Turbopack bundle is broken for the Mol\* route.
- **No new response-shape breaks.** Add optional fields with defaults, as `SecondaryStructurePercentages.available` did.
- **Registry is still in-memory.** Annotations should be fetched on demand and cached, not assumed durable.
- **AGENTS.md holds**: claim-before-code, ≤200 LOC components, full type hints, Pydantic at the boundary, mutation-verified tests.

---

## 6. Honest scope note

This is **substantially larger than the P0–P5 slice** that took this project from nothing to a
working product. P6 alone is comparable to P5. P9's interactive topology viewer, a true atom-mapped
reaction diagram, and a hosted IgBLAST are each their own project.

The plan is therefore ordered so that **stopping after any phase leaves something coherent and
demoable** — the same property that made P0–P5 work. P6 is the phase to prioritise if only one
ships: it answers most of the client's list and fixes the "empty interface" complaint with substance.
