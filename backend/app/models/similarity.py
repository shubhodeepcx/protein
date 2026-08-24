"""API models for UniRef-based "similar proteins" (P8).

The counterpart to BLAST: where a BLAST search computes an alignment on
demand and takes minutes, UniRef is a *precomputed* clustering that UniProt
already publishes, so the same question ("what else looks like this?") is
answerable in one round trip. The panel offers both because they answer
different halves of it — UniRef gives curated homologs instantly, BLAST gives
alignment statistics against a database of your choosing.

Follows the P6 annotation posture: a protein with no resolvable UniProt
accession is a *successful*, empty response with a note explaining why, not an
error the user cannot act on.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# The three clustering levels UniProt publishes. 50% is the default because it
# is the one that actually surfaces cross-species homologs; UniRef100 mostly
# returns the same protein under different accessions.
UNIREF_IDENTITIES: tuple[float, ...] = (0.5, 0.9, 1.0)
DEFAULT_UNIREF_IDENTITY = 0.5


class SimilarProtein(BaseModel):
    """One member of the query protein's UniRef cluster."""

    accession: str = Field(..., description="UniProt accession, e.g. P30406.")
    entry_id: str | None = Field(None, description="UniProtKB entry name, e.g. INS_HUMAN.")
    protein_name: str | None = Field(None, description="Protein name UniRef records.")
    organism: str | None = Field(None, description="Source organism.")
    taxon_id: int | None = Field(None, description="NCBI taxonomy identifier.")
    sequence_length: int | None = Field(None, description="Member sequence length.")
    is_representative: bool = Field(
        False, description="True for the cluster's representative sequence."
    )
    uniprot_url: str | None = Field(None, description="Outbound UniProt entry URL.")


class SimilarProteinsResponse(BaseModel):
    """`GET /api/proteins/{uid}/similar`.

    `members` excludes the query protein itself — a list of "similar proteins"
    whose first entry is the protein you are looking at is noise. `member_count`
    is the cluster's own total, so the UI can still say how big the cluster is.
    """

    id: str = Field(..., description="Local protein uid the homologs belong to.")
    accession: str | None = Field(None, description="Resolved UniProt accession.")
    accession_resolved: bool = Field(
        ..., description="False when no UniProt accession could be resolved."
    )
    resolution_note: str = Field(
        ..., description="How the accession was resolved, or why it could not be."
    )
    identity_threshold: float = Field(
        DEFAULT_UNIREF_IDENTITY,
        description="UniRef clustering level used: 0.5, 0.9 or 1.0.",
    )
    cluster_id: str | None = Field(None, description="UniRef cluster id, e.g. UniRef50_P01308.")
    cluster_name: str | None = Field(None, description="Cluster name, e.g. 'Cluster: Insulin'.")
    member_count: int = Field(0, description="Total members in the cluster, before filtering.")
    organism_count: int = Field(0, description="Distinct organisms in the cluster.")
    members: list[SimilarProtein] = Field(
        default_factory=list, description="Cluster members, query protein excluded."
    )
    truncated: bool = Field(
        False,
        description="True when the cluster holds more members than were returned.",
    )
