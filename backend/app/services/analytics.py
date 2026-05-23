from __future__ import annotations

Composition = dict[str, dict[str, int | float]]
SecondaryStructurePercentages = dict[str, float]
PropertyDistribution = dict[str, int]


def molecular_weight(sequence: str) -> float:
    raise NotImplementedError


def composition(sequence: str) -> Composition:
    raise NotImplementedError


def hydrophobicity_profile(sequence: str, window: int = 9) -> list[float]:
    raise NotImplementedError


def secondary_structure_percentages(structure: object) -> SecondaryStructurePercentages:
    raise NotImplementedError


def property_distribution(sequence: str) -> PropertyDistribution:
    raise NotImplementedError
