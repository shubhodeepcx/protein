"""API models for the P9 complex viewer.

Same posture as `models/annotations.py`: every list defaults to empty and every
scalar to None, so a protein that belongs to no known complex — the normal case
for most structures — still produces a valid `ProteinComplexes`. The frontend
hides a section by asking whether its list is empty, never by branching on a
status code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ComplexParticipant(BaseModel):
    """One member of a macromolecular complex, with its stoichiometry.

    A participant is not necessarily a protein: Complex Portal curates small
    molecules (haem, ATP), RNA, and DNA as first-class participants, which is
    why `interactor_type` is carried rather than assumed.
    """

    identifier: str = Field(
        ...,
        description="Participant identifier — a UniProt accession, a PRO chain id "
        "such as P06213-PRO_0000016689, or a ChEBI id such as CHEBI:30413.",
    )
    name: str = Field("", description="Short label, usually the gene name.")
    description: str | None = Field(None, description="Full participant name.")
    interactor_type: str | None = Field(
        None, description="Complex Portal interactor type, e.g. 'protein'."
    )
    organism: str | None = Field(None, description="Participant organism, when stated.")
    stoichiometry: str | None = Field(
        None,
        description="Copy number for display — '2', or '1-4' for a range. None when "
        "the curators recorded no stoichiometry, which is common.",
    )
    stoichiometry_min: int | None = Field(None, description="Minimum copy number.")
    stoichiometry_max: int | None = Field(None, description="Maximum copy number.")
    url: str | None = Field(None, description="Outbound link to the participant's entry.")
    is_query_protein: bool = Field(
        False,
        description="True for the participant that is the protein being viewed, so "
        "the table can mark which row is 'you'.",
    )


class ProteinComplex(BaseModel):
    """One Complex Portal record the queried protein participates in."""

    accession: str = Field(..., description="Complex Portal accession, e.g. CPX-2158.")
    name: str = Field("", description="Curated complex name.")
    organism: str | None = Field(None, description="Complex organism, e.g. 'Homo sapiens'.")
    description: str | None = Field(
        None,
        description="The curated function of the complex — what the client meant by "
        "'show the functions'.",
    )
    predicted: bool = Field(
        False, description="True for a predicted (not experimentally curated) complex."
    )
    url: str | None = Field(None, description="Complex Portal page for this complex.")
    participants: list[ComplexParticipant] = Field(default_factory=list)


class ProteinComplexes(BaseModel):
    """`GET /api/proteins/{id}/complexes`.

    `accession_resolved` is false for a structure with no UniProt counterpart —
    a plain upload, usually. That is a successful response with no complexes,
    not an error.
    """

    id: str = Field(..., description="Local protein uid the complexes belong to.")
    accession: str | None = Field(None, description="Resolved UniProt accession.")
    accession_resolved: bool = Field(
        ..., description="False when no UniProt accession could be resolved."
    )
    resolution_note: str = Field(
        ..., description="How the accession was resolved, or why it could not be."
    )
    query: str | None = Field(
        None,
        description="The accession actually sent to Complex Portal. Differs from "
        "`accession` for an isoform: Complex Portal indexes base accessions only.",
    )
    complexes: list[ProteinComplex] = Field(
        default_factory=list,
        description="Complexes in which this protein is an actual participant.",
    )
    search_matches: int = Field(
        0,
        description="How many records Complex Portal's free-text index matched for "
        "this accession. Larger than len(complexes) when a complex merely mentions "
        "the accession in its description without containing the protein.",
    )
