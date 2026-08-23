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
