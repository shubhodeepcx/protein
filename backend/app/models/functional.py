"""API models for A5 — functional regions and binding pockets.

Same posture as `models/annotations.py` and `models/complexes.py`: every list
defaults empty and every scalar to None, so a protein with no UniProt entry, no
curated sites and no bound ligand still produces a valid `FunctionalRegions`.

Two things about this payload are load-bearing and are therefore encoded in the
types rather than left to a convention:

**Provenance.** Every item says where it came from. `provenance="uniprot"` is a
curator's claim about the protein; `provenance="structure"` is something
measured in the coordinate file in front of us. They are different kinds of
knowledge and the UI must be able to tell them apart, so they never share a
list and never share a shape.

**Coordinates.** Positions are expressed as `ResidueRef.ordinal` — the 1-based
index of the residue inside the chain's parsed one-letter sequence, which is the
coordinate system `backend/app/services/parser.py` emits and
`frontend/lib/molstar/residue-index.ts` mirrors. It is *not* `auth_seq_id`.
`auth_seq_id` is carried alongside for display only, because that is the number
printed in papers and in the PDB file, and the two are routinely different.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: A curated site's UniProt feature type, normalised to the four we ask for.
SiteKind = Literal["active_site", "binding_site", "site", "dna_binding"]

#: Where a claim came from. Kept as a closed set so the UI cannot invent a third.
Provenance = Literal["uniprot", "structure"]


class ResidueRef(BaseModel):
    """One residue, in the coordinate system the selection seam already uses.

    `key` is exactly what `setSelection` in `lib/store/selection-slice.ts`
    takes, so a click here selects in 3D through the existing machinery rather
    than a second one.
    """

    chain: str = Field(..., description="Author chain label, e.g. 'A'.")
    ordinal: int = Field(
        ...,
        description="1-based index within the chain's parsed sequence. The "
        "selection coordinate. NOT auth_seq_id.",
    )
    key: str = Field(..., description="Selection key, '<chain>:<ordinal>'.")
    residue: str = Field(
        ..., description="One-letter code as the parser read it ('X' if non-standard)."
    )
    auth_seq_id: int | None = Field(
        None, description="Residue number as written in the file. Display only."
    )
    insertion_code: str | None = Field(
        None, description="PDB insertion code, when the residue carries one."
    )


class ChainMapping(BaseModel):
    """How one chain was related to the UniProt sequence — or why it was not.

    This is published rather than kept internal on purpose. A curated position
    placed on the wrong residue is the worst thing this feature can do, so the
    evidence for every placement is part of the response and the UI can show it.
    """

    chain: str = Field(..., description="Author chain label.")
    mapped: bool = Field(
        ..., description="False when no position may be placed on this chain."
    )
    residue_count: int = Field(0, description="Residues the parser read for this chain.")
    aligned_columns: int = Field(
        0, description="Columns with a residue on both sides of the alignment."
    )
    identity_percent: float = Field(
        0.0, description="Identical columns as a percent of aligned columns."
    )
    coverage_percent: float = Field(
        0.0, description="Identical columns as a percent of the chain's length."
    )
    uniprot_start: int | None = Field(
        None, description="First UniProt position this chain covers, when mapped."
    )
    uniprot_end: int | None = Field(
        None, description="Last UniProt position this chain covers, when mapped."
    )
    offset_note: str = Field(
        "",
        description="Plain-language statement of the numbering relationship, e.g. "
        "'UniProt 19-147 covers chain A ordinals 1-129 (auth 1-129)'.",
    )
    note: str = Field("", description="Why the chain was refused, when it was.")


class CuratedSite(BaseModel):
    """One UniProt positional feature, projected onto this structure.

    `located` is the honest half of the model. A crystallised construct is
    routinely a fragment, and disordered residues are simply absent from the
    coordinates, so a curated position frequently has nowhere to go in *this*
    file. That case returns the site with `positions` empty, `located` false and
    a note — never with a guessed position.
    """

    kind: SiteKind = Field(..., description="Normalised UniProt feature type.")
    provenance: Literal["uniprot"] = Field(
        "uniprot", description="Curated by UniProt, not observed here."
    )
    label: str = Field(..., description="Short human label for the site.")
    description: str | None = Field(None, description="UniProt's feature description.")
    ligand: str | None = Field(
        None, description="Bound ligand UniProt names for this site, e.g. 'ATP'."
    )
    ligand_id: str | None = Field(None, description="ChEBI id of that ligand.")
    ligand_part: str | None = Field(
        None, description="The part of the ligand bound, when UniProt narrows it."
    )
    evidence_codes: list[str] = Field(
        default_factory=list, description="ECO evidence codes backing the feature."
    )
    experimental: bool = Field(
        False,
        description="True when at least one evidence code is experimental (ECO:0000269 "
        "or ECO:0007744), i.e. not inferred from a sequence rule.",
    )
    uniprot_start: int = Field(..., description="1-based start in the UniProt sequence.")
    uniprot_end: int = Field(..., description="1-based end in the UniProt sequence.")
    uniprot_residues: str = Field(
        "", description="The UniProt sequence over the feature's span."
    )
    positions: list[ResidueRef] = Field(
        default_factory=list,
        description="Every residue in this structure the feature maps onto. More than "
        "one chain's worth for a homo-oligomer; empty when it could not be placed.",
    )
    located: bool = Field(
        False, description="False when no position could be placed in this structure."
    )
    location_note: str = Field(
        "", description="Why the feature could not be placed, when it could not."
    )
    substitutions: list[str] = Field(
        default_factory=list,
        description="Positions where the structure's residue differs from UniProt's, "
        "e.g. 'A:35 is A here but E in UniProt' — an engineered mutant, or a species "
        "difference. Reported, not hidden, and never a reason to move the marker.",
    )


class LigandContact(ResidueRef):
    """A polymer residue in contact with a ligand bound in this structure."""

    min_distance: float = Field(
        ..., description="Closest heavy-atom distance to the ligand, in angstroms."
    )
    atom_contacts: int = Field(
        0, description="How many residue-atom/ligand-atom pairs fall inside the cutoff."
    )


class BoundLigand(BaseModel):
    """One non-polymer group present in the coordinate file, and what it touches.

    This is an observation, not a prediction: the ligand is in the file and the
    distances are measured. It is the only kind of "pocket" this feature claims.
    """

    component: str = Field(..., description="Chemical component id, e.g. 'NAG'.")
    provenance: Literal["structure"] = Field(
        "structure", description="Observed in the coordinate file."
    )
    chain: str = Field(..., description="Author chain the ligand is written under.")
    auth_seq_id: int | None = Field(None, description="Ligand residue number in the file.")
    insertion_code: str | None = Field(None, description="Insertion code, when present.")
    label: str = Field(..., description="Display label, e.g. 'NAG 1 (chain B)'.")
    atom_count: int = Field(0, description="Heavy atoms modelled for this ligand.")
    single_atom: bool = Field(
        False, description="True for a monatomic ion, so the UI can group them."
    )
    contacts: list[LigandContact] = Field(
        default_factory=list,
        description="Polymer residues within the cutoff, closest first.",
    )


class SurfaceProfile(BaseModel):
    """Per-residue hydropathy, charge and solvent accessibility for one chain.

    Parallel arrays rather than a list of objects: index `i` is ordinal `i + 1`,
    which is the same indexing `ChainInfo.sequence` already uses, and it keeps a
    1200-residue chain to a few kilobytes instead of a few hundred.
    """

    chain: str = Field(..., description="Author chain label.")
    sequence: str = Field(
        "", description="The chain's one-letter sequence, exactly as the parser read it."
    )
    hydropathy: list[float] = Field(
        default_factory=list,
        description="Kyte-Doolittle hydropathy per residue. 0.0 for 'X'.",
    )
    charge: list[int] = Field(
        default_factory=list,
        description="Formal side-chain charge at pH 7: -1 for D/E, +1 for K/R, 0 "
        "otherwise. Histidine is 0 here and is reported separately, because its "
        "pKa sits near neutral and calling it +1 would overstate the claim.",
    )
    relative_accessibility: list[float] = Field(
        default_factory=list,
        description="Solvent-accessible surface area as a fraction of the residue's "
        "theoretical maximum (Tien et al. 2013). Empty when SASA was not computed.",
    )
    surface_exposed: list[bool] = Field(
        default_factory=list,
        description="relative_accessibility >= the exposure threshold. Empty when SASA "
        "was not computed.",
    )
    net_charge: int = Field(0, description="(K + R) - (D + E) over the chain.")
    histidine_count: int = Field(0, description="Histidines, counted but not charged.")
    mean_hydropathy: float = Field(0.0, description="Mean Kyte-Doolittle over the chain.")
    surface_mean_hydropathy: float | None = Field(
        None,
        description="Mean hydropathy over the solvent-exposed residues only — the "
        "'surface hydrophobicity' number. None when SASA was not computed.",
    )
    surface_net_charge: int | None = Field(
        None, description="Net charge over the solvent-exposed residues only."
    )


class PriorityResidue(ResidueRef):
    """A residue flagged as high-priority, with every reason it was flagged.

    There is no score. A score would imply a model that was fitted to something,
    and nothing here was. `reasons` is the whole claim, and `evidence_kinds` is
    just how many independent kinds of evidence converged on this residue —
    which is what the ordering is by.
    """

    reasons: list[str] = Field(
        default_factory=list, description="One line per reason, in provenance order."
    )
    provenance: list[Provenance] = Field(
        default_factory=list,
        description="Distinct provenance kinds among the reasons. Two entries means "
        "a curator and this structure agree.",
    )
    evidence_kinds: int = Field(
        0, description="len(provenance). The sort key, not a probability."
    )
    curated_active_site: bool = Field(False, description="A UniProt active site.")
    curated_binding_site: bool = Field(False, description="A UniProt binding site.")
    ligand_contact: bool = Field(False, description="In contact with a bound ligand.")
    hydropathy: float | None = Field(None, description="Kyte-Doolittle value.")
    charge: int | None = Field(None, description="Formal side-chain charge at pH 7.")
    relative_accessibility: float | None = Field(
        None, description="Relative solvent accessibility, when SASA was computed."
    )


class FunctionalRegions(BaseModel):
    """`GET /api/proteins/{id}/functional-regions`.

    A structure with no UniProt counterpart still gets the structure-derived
    half — bound ligands, their contacts, and the surface profile — because
    those are measured here and do not depend on anyone's database. Only the
    curated lists go empty, and `resolution_note` says why.
    """

    id: str = Field(..., description="Local protein uid.")
    accession: str | None = Field(None, description="Resolved UniProt accession.")
    accession_resolved: bool = Field(
        ..., description="False when no UniProt accession could be resolved."
    )
    resolution_note: str = Field(
        ..., description="How the accession was resolved, or why it could not be."
    )

    chain_mappings: list[ChainMapping] = Field(
        default_factory=list,
        description="Per chain, how UniProt positions were related to residue ordinals.",
    )

    active_sites: list[CuratedSite] = Field(default_factory=list)
    binding_sites: list[CuratedSite] = Field(default_factory=list)
    other_sites: list[CuratedSite] = Field(default_factory=list)
    dna_binding: list[CuratedSite] = Field(default_factory=list)

    ligands: list[BoundLigand] = Field(
        default_factory=list,
        description="Non-polymer groups in the file, waters and in-chain modified "
        "residues excluded, with their contact residues.",
    )
    contact_cutoff: float = Field(
        0.0,
        description="Heavy-atom distance in angstroms that defines a contact. Published "
        "because the residue list means nothing without it.",
    )

    surface: list[SurfaceProfile] = Field(default_factory=list)
    surface_note: str = Field(
        "", description="How accessibility was computed, or why it was not."
    )

    priority_residues: list[PriorityResidue] = Field(
        default_factory=list,
        description="Residues with at least one functional claim against them, most "
        "converging evidence first.",
    )

    unlocated_sites: int = Field(
        0,
        description="Curated sites that exist for this protein but could not be placed "
        "in this structure. Counted so the UI can say so out loud.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Statements the user needs in order to read the rest correctly — "
        "including what this feature does NOT do.",
    )
