"""API models for compounds — the non-protein components of a structure.

A protein in a coordinate file rarely sits alone: DNA or RNA it binds, metal
ions, glycans, cofactors and nucleotides, a substrate or an inhibitor, a free
amino acid, modified residues inside its own chain, and the buffer left over
from crystallisation. `ProteinSummary.chains` is deliberately protein-only, so
every analytic stays an analytic *of the protein*; this payload is where the
rest of the file is described.

Every item is an observation about this file. Contacts reuse A5's
`LigandContact` shape, so a contact residue carries the same selection `key`
the sequence panel and the 3D viewer already use.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.functional import LigandContact

#: How a non-polymer (or in-chain hetero) group is classified. Closed set, so the
#: UI can give each one a fixed label and colour.
CompoundCategory = Literal[
    "ion",
    "carbohydrate",
    "cofactor",
    "ligand",
    "free_amino_acid",
    "modified_residue",
    "additive",
]

NucleicAcidKind = Literal["DNA", "RNA", "DNA/RNA hybrid"]


class CompoundInstance(BaseModel):
    """One copy of a compound, at one place in the file."""

    chain: str = Field(..., description="Author chain label the group is written under.")
    auth_seq_id: int | None = Field(None, description="Residue number in the file.")
    insertion_code: str | None = Field(None, description="PDB insertion code, if any.")
    atom_count: int = Field(..., description="Heavy atoms present in the file.")
    contacts: list[LigandContact] = Field(
        default_factory=list,
        description="Protein residues with a heavy atom within the contact cutoff, "
        "nearest first. Always empty for a modified residue, which is part of the chain.",
    )


class CompoundGroup(BaseModel):
    """Every copy of one chemical component (one three-letter code)."""

    code: str = Field(..., description="Chemical component ID, e.g. 'HEM', 'NAG', 'ZN'.")
    name: str | None = Field(
        None, description="Component name from the file (HETNAM / _chem_comp.name) or a built-in table."
    )
    category: CompoundCategory
    formula: str | None = Field(None, description="Formula as the file declares it.")
    formula_weight: float | None = Field(
        None, description="Formula weight in daltons, when the file declares it (mmCIF)."
    )
    parent_residue: str | None = Field(
        None,
        description="For a modified amino acid: the one-letter code of the standard "
        "residue it derives from, when known (MSE -> 'M').",
    )
    instances: list[CompoundInstance] = Field(default_factory=list)


class NucleicAcidChain(BaseModel):
    """A DNA or RNA strand, with the protein residues it touches."""

    label: str = Field(..., description="Author chain label.")
    kind: NucleicAcidKind
    sequence: str = Field(..., description="One-letter nucleotide sequence (N if unknown).")
    length: int
    gc_fraction: float | None = Field(
        None, description="(G + C) over identified bases; None when there are none."
    )
    composition: dict[str, int] = Field(default_factory=dict, description="Count per base.")
    contacts: list[LigandContact] = Field(
        default_factory=list,
        description="Protein residues within the contact cutoff of any atom of the strand.",
    )


class CompoundsResponse(BaseModel):
    """`GET /api/proteins/{uid}/compounds`."""

    protein_id: str
    contact_cutoff: float = Field(..., description="Heavy-atom contact cutoff in Angstroms.")
    nucleic_acids: list[NucleicAcidChain] = Field(default_factory=list)
    groups: list[CompoundGroup] = Field(default_factory=list)
    water_count: int = Field(0, description="Water molecules in the file. Counted, not listed.")
    notes: list[str] = Field(default_factory=list)
