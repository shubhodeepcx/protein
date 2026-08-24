/**
 * Shared TypeScript types that mirror the Pydantic models in the backend.
 *
 * Keep this file in sync with `backend/app/models/protein.py` — these are
 * the wire-format types the frontend sees from the API. See spec section 5.1.
 */

export type ProteinSource = "uploaded" | "rcsb" | "alphafold" | "uniprot";
export type ProteinFileFormat = "pdb" | "mmcif";

export interface ChainInfo {
  id: string;
  /** One-letter chain label, e.g. "A", "B". */
  label: string;
  /** One-letter amino acid sequence. */
  sequence: string;
  residue_count: number;
}

export interface ProteinSummary {
  /** Server-assigned UUID for this protein. */
  id: string;
  source: ProteinSource;
  /** PDB ID, UniProt accession, etc. — null for uploaded files. */
  source_id: string | null;
  name: string | null;
  organism: string | null;
  /** Relative URL the viewer should load the structure from. */
  file_url: string;
  file_format: ProteinFileFormat;
  chains: ChainInfo[];
  residue_count: number;
  atom_count: number;
  /** Daltons. */
  molecular_weight: number;
  /** True when B-factor field contains pLDDT (AlphaFold). */
  has_plddt: boolean;
  warnings: string[];
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  version?: string;
}

export interface CompositionEntry {
  aa: string;
  label: string;
  count: number;
  percent: number;
}

export interface SecondaryStructurePercentages {
  helix: number;
  sheet: number;
  coil: number;
  /**
   * False when the structure file declared no secondary structure at all — an
   * AlphaFold model is the usual case. The helix/sheet/coil split is then an
   * all-coil placeholder, not a measurement, and any surface that draws it
   * must say so. Required on purpose: the backend has always sent the field
   * (it defaults to `true`), and making it optional here is exactly how the
   * donut came to render "100% coil" as if it were a finding.
   */
  available: boolean;
}

export interface HydrophobicityProfile {
  chain_id: string;
  window: number;
  values: number[];
}

export interface PropertyDistribution {
  hydrophobic: number;
  polar: number;
  charged_positive: number;
  charged_negative: number;
  aromatic: number;
  cysteine: number;
}

export interface ChainLength {
  chain_id: string;
  length: number;
}

export interface AnalyticsResponse {
  id: string;
  molecular_weight: number;
  residue_count: number;
  atom_count: number;
  chain_count: number;
  composition: CompositionEntry[];
  secondary_structure: SecondaryStructurePercentages;
  hydrophobicity: HydrophobicityProfile;
  property_distribution: PropertyDistribution;
  chain_lengths: ChainLength[];
}

/* ------------------------------------------------------------------------ */
/* P5 — public database search + import                                       */
/* Mirrors `backend/app/models/search.py`. See spec sections 5.4 and 6.2.     */
/* ------------------------------------------------------------------------ */

/** The public databases `GET /api/search` can query. */
export type SearchSource = "rcsb" | "alphafold" | "uniprot";

/** Value of the `source` query parameter; "all" fans out to every source. */
export type SearchSourceFilter = "all" | SearchSource;

export interface SearchResult {
  source: SearchSource;
  /** PDB ID (RCSB) or UniProt accession (AlphaFold / UniProt). */
  source_id: string;
  title: string | null;
  organism: string | null;
  description: string | null;
  /** Angstroms — RCSB experimental entries only. */
  resolution: number | null;
  /** Experimental or predictive method, e.g. "X-ray", "AlphaFold prediction". */
  method: string | null;
  release_year: number | null;
  sequence_length: number | null;
  /** Mean pLDDT (0-100) for AlphaFold predictions. */
  confidence: number | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  /** Sources that raised — their hits are missing from `results`. */
  failed_sources: SearchSource[];
}

/** Body for `POST /api/proteins/import`. */
export interface ImportRequest {
  source: SearchSource;
  source_id: string;
}

/* ------------------------------------------------------------------------ */
/* P6 — UniProt annotations                                                   */
/* Mirrors `backend/app/models/annotations.py`. Every list is always present  */
/* (possibly empty), so the panel decides what to render by asking whether a  */
/* list is empty — never by branching on a status code.                       */
/* ------------------------------------------------------------------------ */

export interface GoTerm {
  /** e.g. "GO:0005615". */
  id: string;
  /** Term label with UniProt's aspect prefix already stripped. */
  term: string;
  /** GO evidence code, e.g. "IDA". */
  evidence: string | null;
}

export interface GeneOntology {
  biological_process: GoTerm[];
  cellular_component: GoTerm[];
  molecular_function: GoTerm[];
}

export interface CatalyticActivity {
  reaction: string | null;
  ec_number: string | null;
  /** e.g. ["RHEA:10596"]. */
  rhea_ids: string[];
  /** ChEBI ids for the reaction participants. */
  chebi_ids: string[];
}

export interface SubcellularLocation {
  location: string;
  topology: string | null;
}

export interface SequenceFeature {
  /** UniProt feature type, e.g. "Transmembrane". */
  type: string;
  description: string | null;
  /** 1-based, inclusive. */
  start: number | null;
  end: number | null;
}

export interface DiseaseAssociation {
  name: string;
  acronym: string | null;
  description: string | null;
  /** OMIM identifier when UniProt cross-references one. */
  mim_id: string | null;
}

export interface KeywordEntry {
  id: string | null;
  name: string;
  category: string | null;
}

export interface CrossReference {
  database: string;
  id: string;
  description: string | null;
  url: string | null;
}

/* ------------------------------------------------------------------------ */
/* P7 — comparison view (spec A3)                                             */
/* Mirrors `backend/app/models/compare.py`. Delta convention, without          */
/* exception: `delta = b - a`. Positive means B has more of it.                */
/* ------------------------------------------------------------------------ */

/** Body for `POST /api/compare`. Chains default to each protein's longest. */
export interface CompareRequest {
  a: string;
  b: string;
  chain_a?: string;
  chain_b?: string;
}

/** Narrow projection of `ProteinSummary` — enough to label and load one side. */
export interface CompareProteinRef {
  id: string;
  source: ProteinSource;
  source_id: string | null;
  name: string | null;
  organism: string | null;
  file_url: string;
  file_format: ProteinFileFormat;
  has_plddt: boolean;
}

export interface MetricDelta {
  key: string;
  label: string;
  /** e.g. "Da". Null when the metric is a bare count. */
  unit: string | null;
  a: number;
  b: number;
  delta: number;
}

/**
 * Chains are paired by descending length, not by label — two structures of the
 * same protein routinely label them differently. A side with fewer chains
 * reports null rather than dropping the row.
 */
export interface ChainLengthPair {
  rank: number;
  chain_a: string | null;
  length_a: number | null;
  chain_b: string | null;
  length_b: number | null;
  delta: number | null;
}

export interface CompositionDelta {
  aa: string;
  label: string;
  count_a: number;
  count_b: number;
  percent_a: number;
  percent_b: number;
  /** Percentage points, not counts — the only figure comparable across sizes. */
  delta_percent: number;
}

export interface SecondaryStructureDelta {
  helix_a: number;
  helix_b: number;
  helix_delta: number;
  sheet_a: number;
  sheet_b: number;
  sheet_delta: number;
  coil_a: number;
  coil_b: number;
  coil_delta: number;
  /** False means that side declared no secondary structure — the split is a
   *  placeholder and the deltas on this row mean nothing. */
  available_a: boolean;
  available_b: boolean;
}

export interface SequenceAlignment {
  chain_a: string;
  chain_b: string;
  length_a: number;
  length_b: number;
  /** Total columns, gaps included. */
  alignment_length: number;
  /** Columns where neither side is a gap. */
  aligned_columns: number;
  identities: number;
  similarities: number;
  gap_columns: number;
  /** identities / alignment_length — what EMBOSS needle prints. */
  identity_percent: number;
  similarity_percent: number;
  /** identities / aligned_columns — "how similar is the shared part". */
  identity_percent_aligned: number;
  score: number;
  aligned_a: string;
  aligned_b: string;
  /** '|' identity, '+' similar, ' ' otherwise. Same length as the rows. */
  match_line: string;
}

export interface Superposition {
  chain_a: string;
  chain_b: string;
  /** Angstroms, over the paired alpha carbons. */
  rmsd: number;
  atom_pairs: number;
  residue_pairs: number;
  identity_percent: number;
  /** Set when the RMSD is real but should not be read at face value. */
  caveat: string | null;
}

export interface CompareResponse {
  a: CompareProteinRef;
  b: CompareProteinRef;
  metrics: MetricDelta[];
  chain_lengths: ChainLengthPair[];
  composition: CompositionDelta[];
  secondary_structure: SecondaryStructureDelta;
  /** Null when no chain pair could be aligned — `alignment_note` says why. */
  alignment: SequenceAlignment | null;
  alignment_note: string;
  /** Null when the RMSD was refused — `superposition_note` says why. */
  superposition: Superposition | null;
  superposition_note: string;
}

export interface ProteinAnnotations {
  id: string;
  accession: string | null;
  /** False for a protein with no UniProt counterpart — an upload, usually. */
  accession_resolved: boolean;
  /** How the accession was resolved, or why it could not be. Shown to the user. */
  resolution_note: string;
  entry_name: string | null;
  protein_name: string | null;
  gene_names: string[];
  organism: string | null;
  taxon_id: number | null;
  lineage: string[];
  function: string[];
  catalytic_activity: CatalyticActivity[];
  gene_ontology: GeneOntology;
  keywords: KeywordEntry[];
  subcellular_locations: SubcellularLocation[];
  subcellular_location_notes: string[];
  transmembrane: SequenceFeature[];
  diseases: DiseaseAssociation[];
  ptm: string[];
  ptm_features: SequenceFeature[];
  cross_references: CrossReference[];
}

/** Mirrors `backend/app/models/complexes.py` (P9). */
export interface ComplexParticipant {
  /** A UniProt accession, a PRO chain id, or a ChEBI id for a small molecule. */
  identifier: string;
  name: string;
  description: string | null;
  /** Complex Portal interactor type — "protein", "small molecule", RNA kinds. */
  interactor_type: string | null;
  organism: string | null;
  /** "2", or "0-1" for an optional participant. Null when not curated. */
  stoichiometry: string | null;
  stoichiometry_min: number | null;
  stoichiometry_max: number | null;
  url: string | null;
  /** True for the row that is the protein currently open in the viewer. */
  is_query_protein: boolean;
}

export interface ProteinComplex {
  /** Complex Portal accession, e.g. "CPX-2158". */
  accession: string;
  name: string;
  organism: string | null;
  /** The curated function of the complex. Predicted complexes have none. */
  description: string | null;
  predicted: boolean;
  url: string | null;
  participants: ComplexParticipant[];
}

export interface ProteinComplexes {
  id: string;
  accession: string | null;
  accession_resolved: boolean;
  resolution_note: string;
  /** The base accession actually sent to Complex Portal. */
  query: string | null;
  complexes: ProteinComplex[];
  /**
   * How many records Complex Portal's free-text index matched. Larger than
   * `complexes.length` when a complex merely names the accession in its
   * description without containing the protein.
   */
  search_matches: number;
}

/* ------------------------------------------------------------------------ */
/* P8 — sequence similarity: BLAST and UniRef homologs                        */
/* Mirrors `backend/app/models/blast.py` and `models/similarity.py`.          */
/*                                                                            */
/* BLAST is the project's only ASYNCHRONOUS flow: `POST /api/blast` returns   */
/* a job id, and `GET /api/blast/{job_id}` is polled until `finished` is      */
/* true. A search takes 30 s to several minutes.                              */
/* ------------------------------------------------------------------------ */

/** The four programs EBI's REST service exposes. blastp is our default. */
export type BlastProgram = "blastp" | "blastn" | "tblastn" | "blastx";

/** EBI's job states, plus NOT_FOUND for an expired or unknown job. */
export type BlastStatus =
  | "QUEUED"
  | "RUNNING"
  | "FINISHED"
  | "FAILURE"
  | "ERROR"
  | "NOT_FOUND";

/** Body for `POST /api/blast`. Exactly one of protein_id / sequence. */
export interface BlastSubmitRequest {
  protein_id?: string;
  /** Chain label to query with. Omitted means the longest chain. */
  chain_id?: string;
  sequence?: string;
  program?: BlastProgram;
  database?: string;
  /** E-value threshold as a string, e.g. "1e-3". */
  exp?: string;
  alignments?: number;
  scores?: number;
  matrix?: string;
  filter_low_complexity?: boolean;
}

/** The submit round trip. Carries a job id and nothing else of substance. */
export interface BlastSubmitResponse {
  job_id: string;
  status: BlastStatus;
  program: BlastProgram;
  database: string;
  query_length: number;
  /** Where the query came from, e.g. "1CRN chain A". */
  query_source: string;
  /** ISO-8601 UTC. */
  submitted_at: string;
  poll_url: string;
}

export interface BlastHsp {
  rank: number;
  score: number | null;
  bit_score: number | null;
  expect: number | null;
  align_length: number | null;
  identity_percent: number | null;
  positive_percent: number | null;
  gaps: number | null;
  query_start: number | null;
  query_end: number | null;
  hit_start: number | null;
  hit_end: number | null;
}

export interface BlastHit {
  rank: number;
  accession: string;
  entry_id: string | null;
  description: string | null;
  database: string | null;
  organism: string | null;
  gene: string | null;
  length: number | null;
  url: string | null;
  /**
   * Accession to import by, or null when the hit is not a UniProt entry.
   * Null is what stops the UI offering an Open button that could only fail.
   */
  uniprot_accession: string | null;
  /** Summary of the BEST HSP, chosen by score. */
  identity_percent: number | null;
  expect: number | null;
  score: number | null;
  bit_score: number | null;
  align_length: number | null;
  gaps: number | null;
  hsps: BlastHsp[];
}

export interface BlastResult {
  program: string | null;
  version: string | null;
  databases: string[];
  query_id: string | null;
  query_definition: string | null;
  query_length: number | null;
  hit_count: number;
  hits: BlastHit[];
  started_at: string | null;
  finished_at: string | null;
}

/** `GET /api/blast/{job_id}`. `result` is non-null only once FINISHED. */
export interface BlastJobStatus {
  job_id: string;
  status: BlastStatus;
  /** True once the status will not change again — stop polling. */
  finished: boolean;
  program: BlastProgram;
  database: string;
  query_length: number;
  query_source: string;
  submitted_at: string;
  /** Seconds since submission — real progress, not a guess. */
  elapsed_seconds: number;
  poll_count: number;
  message: string;
  result: BlastResult | null;
}

export interface SimilarProtein {
  accession: string;
  entry_id: string | null;
  protein_name: string | null;
  organism: string | null;
  taxon_id: number | null;
  sequence_length: number | null;
  is_representative: boolean;
  uniprot_url: string | null;
}

/** `GET /api/proteins/{uid}/similar` — precomputed UniRef homologs. */
export interface SimilarProteinsResponse {
  id: string;
  accession: string | null;
  accession_resolved: boolean;
  resolution_note: string;
  /** UniRef clustering level: 0.5, 0.9 or 1.0. */
  identity_threshold: number;
  cluster_id: string | null;
  cluster_name: string | null;
  /** Total members in the cluster, before the query and UniParc rows are dropped. */
  member_count: number;
  organism_count: number;
  members: SimilarProtein[];
  truncated: boolean;
}

/**
 * A5 — functional regions and binding pockets.
 *
 * Two kinds of claim live in this payload and they are never mixed.
 * `provenance: "uniprot"` is a curator's statement about the protein;
 * `provenance: "structure"` is something measured in the coordinate file. The
 * UI has to be able to tell them apart, so they never share a type.
 *
 * Every position is a `ResidueRef.ordinal` — the 1-based index inside the
 * chain's parsed sequence, the coordinate `lib/residue.ts` documents and
 * `setSelection` consumes. It is NOT `auth_seq_id`; that is carried alongside
 * for display, because the two are routinely different.
 */
export interface ResidueRef {
  chain: string;
  ordinal: number;
  /** `"<chain>:<ordinal>"` — exactly what `setSelection` takes. */
  key: string;
  residue: string;
  auth_seq_id: number | null;
  insertion_code: string | null;
}

/** How one chain was related to the UniProt sequence — or why it was not. */
export interface ChainMapping {
  chain: string;
  mapped: boolean;
  residue_count: number;
  aligned_columns: number;
  identity_percent: number;
  coverage_percent: number;
  uniprot_start: number | null;
  uniprot_end: number | null;
  offset_note: string;
  note: string;
}

export type SiteKind = "active_site" | "binding_site" | "site" | "dna_binding";

/** A UniProt positional feature, placed on this structure or explicitly not. */
export interface CuratedSite {
  kind: SiteKind;
  provenance: "uniprot";
  label: string;
  description: string | null;
  ligand: string | null;
  ligand_id: string | null;
  ligand_part: string | null;
  evidence_codes: string[];
  experimental: boolean;
  uniprot_start: number;
  uniprot_end: number;
  uniprot_residues: string;
  positions: ResidueRef[];
  /** False when the site could not be placed. `positions` is then empty. */
  located: boolean;
  location_note: string;
  substitutions: string[];
}

export interface LigandContact extends ResidueRef {
  min_distance: number;
  atom_contacts: number;
}

/** A non-polymer group present in the file, and the residues it touches. */
export interface BoundLigand {
  component: string;
  provenance: "structure";
  chain: string;
  auth_seq_id: number | null;
  insertion_code: string | null;
  label: string;
  atom_count: number;
  single_atom: boolean;
  contacts: LigandContact[];
}

/**
 * Per-residue chemistry for one chain, as parallel arrays: index `i` is
 * ordinal `i + 1`, the same indexing `ChainInfo.sequence` uses.
 *
 * `relative_accessibility` and `surface_exposed` are empty when the
 * Shrake-Rupley pass was skipped; `surface_note` then says why.
 */
export interface SurfaceProfile {
  chain: string;
  sequence: string;
  hydropathy: number[];
  charge: number[];
  relative_accessibility: number[];
  surface_exposed: boolean[];
  net_charge: number;
  histidine_count: number;
  mean_hydropathy: number;
  surface_mean_hydropathy: number | null;
  surface_net_charge: number | null;
}

/** A residue with at least one functional claim against it. No score. */
export interface PriorityResidue extends ResidueRef {
  reasons: string[];
  provenance: ("uniprot" | "structure")[];
  /** How many independent kinds of evidence converged. The sort key. */
  evidence_kinds: number;
  curated_active_site: boolean;
  curated_binding_site: boolean;
  ligand_contact: boolean;
  hydropathy: number | null;
  charge: number | null;
  relative_accessibility: number | null;
}

/** `GET /api/proteins/{uid}/functional-regions`. */
export interface FunctionalRegions {
  id: string;
  accession: string | null;
  accession_resolved: boolean;
  resolution_note: string;
  chain_mappings: ChainMapping[];
  active_sites: CuratedSite[];
  binding_sites: CuratedSite[];
  other_sites: CuratedSite[];
  dna_binding: CuratedSite[];
  ligands: BoundLigand[];
  /** Heavy-atom distance, in angstroms, that defines a contact. */
  contact_cutoff: number;
  surface: SurfaceProfile[];
  surface_note: string;
  priority_residues: PriorityResidue[];
  unlocated_sites: number;
  notes: string[];
}
