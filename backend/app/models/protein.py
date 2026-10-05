from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChainInfo(BaseModel):
    """Summary metadata for one parsed protein chain."""

    id: str = Field(..., description="Stable chain identifier.")
    label: str = Field(..., description="Display label such as A or B.")
    sequence: str = Field(..., description="One-letter amino-acid sequence.")
    residue_count: int = Field(..., description="Number of residues in the chain.")


class ProteinSummary(BaseModel):
    """API-facing summary for uploaded or imported protein structures."""

    id: str = Field(..., description="UUID for the locally stored protein.")
    source: Literal["uploaded", "rcsb", "alphafold", "uniprot"] = Field(
        ..., description="Protein source."
    )
    source_id: str | None = Field(None, description="PDB ID or UniProt accession.")
    name: str | None = Field(None, description="Protein name when known.")
    organism: str | None = Field(None, description="Source organism when known.")
    file_url: str = Field(..., description="API URL for the structure file.")
    file_format: Literal["pdb", "mmcif"] = Field(..., description="Stored structure format.")
    chains: list[ChainInfo] = Field(..., description="Parsed protein chains.")
    residue_count: int = Field(..., description="Total residue count.")
    atom_count: int = Field(..., description="Total atom count.")
    molecular_weight: float = Field(..., description="Molecular weight in daltons.")
    has_plddt: bool = Field(..., description="Whether pLDDT values are present.")
    warnings: list[str] = Field(..., description="Non-fatal parser warnings.")
    nucleic_acid_chains: list[str] = Field(
        default_factory=list,
        description=(
            "Labels of DNA/RNA chains. Kept out of `chains` (which is protein-only) "
            "and described in full by `/compounds`."
        ),
    )
