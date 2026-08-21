from __future__ import annotations

from pydantic import BaseModel, Field


class CompositionEntry(BaseModel):
    """One amino-acid entry in the composition breakdown."""

    aa: str = Field(..., description="One-letter amino acid code.")
    label: str = Field(..., description="Three-letter code, e.g. 'Ala'.")
    count: int = Field(..., description="Number of residues of this type.")
    percent: float = Field(..., description="Percent of total residues (0-100).")


class SecondaryStructurePercentages(BaseModel):
    helix: float = Field(..., description="Fraction in helix (0-1).")
    sheet: float = Field(..., description="Fraction in sheet (0-1).")
    coil: float = Field(..., description="Fraction in coil (0-1).")
    # Optional with a `True` default on purpose: every existing consumer keeps
    # working unchanged, and only a client that looks for the flag learns that
    # the numbers are a placeholder.
    available: bool = Field(
        True,
        description=(
            "Whether the structure file declared any secondary structure. False "
            "means none was annotated (an AlphaFold prediction, for example, has "
            "no assigned secondary structure), so the helix/sheet/coil split "
            "above is an all-coil placeholder rather than a measurement."
        ),
    )


class HydrophobicityProfile(BaseModel):
    chain_id: str = Field(
        ..., description="Chain label the profile was computed on (longest chain)."
    )
    window: int = Field(..., description="Sliding window size.")
    values: list[float] = Field(
        ...,
        description=(
            "One value per window-center position; "
            "length == residue_count - window + 1."
        ),
    )


class PropertyDistribution(BaseModel):
    hydrophobic: int = 0
    polar: int = 0
    charged_positive: int = 0
    charged_negative: int = 0
    aromatic: int = 0
    cysteine: int = 0


class ChainLength(BaseModel):
    chain_id: str
    length: int


class AnalyticsResponse(BaseModel):
    """Full analytics payload for one protein."""

    id: str
    molecular_weight: float
    residue_count: int
    atom_count: int
    chain_count: int
    composition: list[CompositionEntry]
    secondary_structure: SecondaryStructurePercentages
    hydrophobicity: HydrophobicityProfile
    property_distribution: PropertyDistribution
    chain_lengths: list[ChainLength]
