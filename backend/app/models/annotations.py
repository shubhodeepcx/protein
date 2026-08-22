"""API models for the P6 annotation panel.

Every list defaults to empty and every scalar to None: a protein with no
resolvable UniProt accession must still produce a valid `ProteinAnnotations`,
and the frontend hides a section by asking whether its list is empty rather
than by branching on a status code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoTerm(BaseModel):
    """One Gene Ontology annotation, already sorted into its aspect."""

    id: str = Field(..., description="GO identifier, e.g. GO:0005615.")
    term: str = Field(..., description="Term label without its aspect prefix.")
    evidence: str | None = Field(None, description="GO evidence code, e.g. IDA.")


class GeneOntology(BaseModel):
    """GO annotations grouped by the ontology's three aspects.

    UniProt splits these across the `go_p` / `go_c` / `go_f` return fields but
    delivers them as one cross-reference list whose terms carry a `P:` / `C:` /
    `F:` prefix — that prefix is what this grouping reads.
    """

    biological_process: list[GoTerm] = Field(default_factory=list)
    cellular_component: list[GoTerm] = Field(default_factory=list)
    molecular_function: list[GoTerm] = Field(default_factory=list)


class CatalyticActivity(BaseModel):
    """One catalysed reaction, with the identifiers needed to link out."""

    reaction: str | None = Field(None, description="Human-readable reaction text.")
    ec_number: str | None = Field(None, description="Enzyme Commission number.")
    rhea_ids: list[str] = Field(
        default_factory=list, description="Rhea reaction ids, e.g. RHEA:12345."
    )
    chebi_ids: list[str] = Field(
        default_factory=list, description="ChEBI ids for the reaction participants."
    )


class SubcellularLocation(BaseModel):
    location: str = Field(..., description="Location term, e.g. 'Secreted'.")
    topology: str | None = Field(None, description="Membrane topology when stated.")


class SequenceFeature(BaseModel):
    """A positional annotation — transmembrane span, chain, disulfide bond, …"""

    type: str = Field(..., description="UniProt feature type, e.g. 'Transmembrane'.")
    description: str | None = Field(None, description="Feature description.")
    start: int | None = Field(None, description="1-based start position.")
    end: int | None = Field(None, description="1-based end position.")


class DiseaseAssociation(BaseModel):
    name: str = Field(..., description="Disease name.")
    acronym: str | None = Field(None, description="UniProt disease acronym.")
    description: str | None = Field(None, description="Disease description.")
    mim_id: str | None = Field(None, description="OMIM identifier when cross-referenced.")


class KeywordEntry(BaseModel):
    id: str | None = Field(None, description="Keyword accession, e.g. KW-0372.")
    name: str = Field(..., description="Keyword label.")
    category: str | None = Field(None, description="UniProt keyword category.")


class CrossReference(BaseModel):
    """An outbound link to a pathway / network / proteome database."""

    database: str = Field(..., description="Database name as UniProt spells it.")
    id: str = Field(..., description="Identifier within that database.")
    description: str | None = Field(None, description="Label UniProt ships with the id.")
    url: str | None = Field(None, description="Resolved outbound URL, when known.")


class ProteinAnnotations(BaseModel):
    """`GET /api/proteins/{id}/annotations`.

    `accession_resolved` is false for a plain upload with no UniProt
    counterpart. That is a successful response with empty sections, not an
    error: there is nothing wrong, there is just nothing to show.
    """

    id: str = Field(..., description="Local protein uid the annotations belong to.")
    accession: str | None = Field(None, description="Resolved UniProt accession.")
    accession_resolved: bool = Field(
        ..., description="False when no UniProt accession could be resolved."
    )
    resolution_note: str = Field(
        ..., description="How the accession was resolved, or why it could not be."
    )

    entry_name: str | None = Field(None, description="UniProtKB entry name, e.g. INS_HUMAN.")
    protein_name: str | None = Field(None, description="Recommended protein name.")
    gene_names: list[str] = Field(default_factory=list)
    organism: str | None = Field(None, description="Scientific name of the organism.")
    taxon_id: int | None = Field(None, description="NCBI taxonomy identifier.")
    lineage: list[str] = Field(default_factory=list, description="Taxonomic lineage.")

    function: list[str] = Field(
        default_factory=list, description="Free-text FUNCTION comment paragraphs."
    )
    catalytic_activity: list[CatalyticActivity] = Field(default_factory=list)
    gene_ontology: GeneOntology = Field(default_factory=GeneOntology)
    keywords: list[KeywordEntry] = Field(default_factory=list)
    subcellular_locations: list[SubcellularLocation] = Field(default_factory=list)
    subcellular_location_notes: list[str] = Field(default_factory=list)
    transmembrane: list[SequenceFeature] = Field(
        default_factory=list, description="Transmembrane spans and topological domains."
    )
    diseases: list[DiseaseAssociation] = Field(default_factory=list)
    ptm: list[str] = Field(
        default_factory=list, description="Free-text PTM comment paragraphs."
    )
    ptm_features: list[SequenceFeature] = Field(
        default_factory=list,
        description="Signal peptides, chains, modified residues, disulfide bonds.",
    )
    cross_references: list[CrossReference] = Field(default_factory=list)
