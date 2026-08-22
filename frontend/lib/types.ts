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
