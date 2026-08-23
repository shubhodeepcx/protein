"""Generates the five `superpose_*.pdb` fixtures used by `tests/test_compare.py`.

Run offline; the files it writes are committed. Nothing in the test suite
imports this module — it exists so the fixtures' provenance is auditable and so
the coordinates can be regenerated without hand-editing PDB columns:

    cd backend && python tests/fixtures/make_superposition_fixtures.py

## What these fixtures are for

`services/compare.py` computes an RMSD by pairing residues through a sequence
alignment. The risk is not the least-squares fit — that is BioPython's
`Superimposer`, trusted library code — it is the *pairing*: an off-by-one, or a
pairing that ignores alignment gaps, produces a confident and completely wrong
number.

So every fixture below is a rigid transform of one reference set of coordinates.
A rigid transform has an exact expected answer — RMSD 0 — which a correct
pairing reaches and an incorrect one cannot. The transform (a 30-degree rotation
about z, then a translation well away from the origin) is there so that reaching
0 requires actually solving for the rotation, not merely subtracting identical
numbers.

## The five files

| File | Chain A sequence | Role |
|---|---|---|
| `superpose_ref.pdb` | `ACDEFGHI` | The reference. Every other file is this one, transformed. |
| `superpose_rigid.pdb` | `ACDEFGHI` | Ungapped control: 8 pairs, RMSD 0. |
| `superpose_gapped.pdb` | `ACDGHI` | Residues 4 and 5 (E, F) deleted. The alignment must place a 2-column gap; index-to-index pairing would mispair the last three residues and blow the RMSD up. |
| `superpose_noca.pdb` | `ACDGHI` | `superpose_gapped.pdb` with one residue modelled without its alpha carbon: 6 residue pairs but only 5 atom pairs. |
| `superpose_short.pdb` | `AC` | Only two residues can pair — below the minimum for a determined rotation, so the fit must be refused rather than reported. |

Only alpha carbons are emitted. The comparison pairs on CA and nothing else, and
a backbone that is not read is a backbone that cannot be got wrong.
"""

from __future__ import annotations

import math
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# One-letter -> three-letter, for the residues these fixtures use.
THREE_LETTER = {
    "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU",
    "F": "PHE", "G": "GLY", "H": "HIS", "I": "ILE",
}

REFERENCE_SEQUENCE = "ACDEFGHI"

# A right-handed helical arc: non-collinear and non-planar, so the optimal
# rotation is uniquely determined. Collinear points would leave a whole axis of
# rotation free and make "RMSD 0" reachable by a wrong fit.
HELIX_RADIUS = 2.3
HELIX_RISE = 1.5
HELIX_TURN_DEGREES = 100.0

# The rigid transform every non-reference fixture carries.
ROTATION_DEGREES = 30.0
TRANSLATION = (7.0, -3.0, 11.0)


def reference_coordinates() -> list[tuple[float, float, float]]:
    """One CA position per residue of `REFERENCE_SEQUENCE`."""
    coords: list[tuple[float, float, float]] = []
    for i in range(len(REFERENCE_SEQUENCE)):
        angle = math.radians(HELIX_TURN_DEGREES * i)
        coords.append(
            (
                round(HELIX_RADIUS * math.cos(angle), 3),
                round(HELIX_RADIUS * math.sin(angle), 3),
                round(HELIX_RISE * i, 3),
            )
        )
    return coords


def rigidly_transform(
    coords: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Rotate about z by `ROTATION_DEGREES`, then translate by `TRANSLATION`."""
    angle = math.radians(ROTATION_DEGREES)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    moved: list[tuple[float, float, float]] = []
    for x, y, z in coords:
        moved.append(
            (
                round(x * cos_a - y * sin_a + TRANSLATION[0], 3),
                round(x * sin_a + y * cos_a + TRANSLATION[1], 3),
                round(z + TRANSLATION[2], 3),
            )
        )
    return moved


def write_pdb(
    path: Path,
    sequence: str,
    coords: list[tuple[float, float, float]],
    *,
    title: str,
    atom_names: list[str] | None = None,
) -> None:
    """Emit one CA-only PDB with chain A numbered from 1.

    `atom_names` defaults to CA for every residue; pass it to model a residue
    without its alpha carbon.
    """
    names = atom_names or ["CA"] * len(sequence)
    lines = ["HEADER    SUPERPOSITION FIXTURE                   01-JAN-00   0SUP",
             f"TITLE     {title}"]
    for serial, (one_letter, (x, y, z), atom_name) in enumerate(
        zip(sequence, coords, names), start=1
    ):
        resname = THREE_LETTER[one_letter]
        element = atom_name[0]
        # PDB v3.3 fixed columns: 7-11 serial, 13-16 atom name (a one-character
        # element sits at 14, hence the centring), 17 altLoc, 18-20 resName,
        # 22 chainID, 23-26 resSeq, 27 iCode, then x/y/z from column 31.
        lines.append(
            f"ATOM  {serial:>5} {atom_name:^4} {resname:>3} A{serial:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 10.00          {element:>2}"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    reference = reference_coordinates()
    transformed = rigidly_transform(reference)

    write_pdb(
        OUT_DIR / "superpose_ref.pdb",
        REFERENCE_SEQUENCE,
        reference,
        title="REFERENCE HELICAL ARC, CHAIN A, 8 RESIDUES",
    )
    write_pdb(
        OUT_DIR / "superpose_rigid.pdb",
        REFERENCE_SEQUENCE,
        transformed,
        title="REFERENCE ROTATED 30 DEG ABOUT Z AND TRANSLATED",
    )

    # Drop E and F (indices 3 and 4). The kept residues carry their transformed
    # coordinates unchanged, so a gap-aware pairing still fits them exactly.
    kept = [0, 1, 2, 5, 6, 7]
    gapped_sequence = "".join(REFERENCE_SEQUENCE[i] for i in kept)
    gapped_coords = [transformed[i] for i in kept]
    write_pdb(
        OUT_DIR / "superpose_gapped.pdb",
        gapped_sequence,
        gapped_coords,
        title="TRANSFORMED REFERENCE WITH RESIDUES 4-5 DELETED",
    )

    # Same again, but the third residue is modelled without its alpha carbon.
    # Its backbone nitrogen stands in so the residue still parses into the
    # sequence — it is present, it simply cannot be fitted.
    no_ca_names = ["CA", "CA", "N", "CA", "CA", "CA"]
    write_pdb(
        OUT_DIR / "superpose_noca.pdb",
        gapped_sequence,
        gapped_coords,
        title="AS GAPPED, WITH ONE RESIDUE MISSING ITS ALPHA CARBON",
        atom_names=no_ca_names,
    )

    write_pdb(
        OUT_DIR / "superpose_short.pdb",
        REFERENCE_SEQUENCE[:2],
        transformed[:2],
        title="TWO RESIDUES ONLY, TOO FEW TO DETERMINE A ROTATION",
    )

    for name in (
        "superpose_ref.pdb",
        "superpose_rigid.pdb",
        "superpose_gapped.pdb",
        "superpose_noca.pdb",
        "superpose_short.pdb",
    ):
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
