"""Generates the matched `parity_multichain.pdb` / `parity_multichain.cif` pair.

Run offline; the two files it writes are committed. Nothing in the test suite
imports this module — it exists so the fixture's provenance is auditable and so
the pair can be regenerated or extended without hand-editing coordinates:

    cd backend && python tests/fixtures/make_parity_fixture.py

## Why the fixture is built rather than downloaded

`tests/test_parser_parity.py` asks whether `PDBParser` and `MMCIFParser` agree
on chain labels and per-chain residue ordering. Answering that needs the SAME
structure in both formats. Downloading `4HHB.pdb` and `4HHB.cif` from RCSB
would give two files RCSB derived independently — a mismatch could then be
RCSB's, not ours — and AGENTS.md forbids tests that reach a live API. So both
files are emitted here from one in-memory residue list: any parse difference is
a parser difference by construction.

## What the structure is designed to break

Every feature below is a case where a naive implementation would disagree with
the other format, or where the frontend's Mol*-side mirror
(`frontend/lib/molstar/residue-index.ts`) would drift from the backend:

* **Chain H** starts at author residue 27, not 1, and has a gap (30-33
  unmodelled) and an insertion code (34, 34A). Any code that treats
  `auth_seq_id` as the sequence ordinal produces the wrong answer.
* **MSE at H/29** is `group_PDB = HETATM` while sitting inside the polymer,
  exactly as RCSB codes selenomethionine. Both parsers must skip it, or chain
  H's ordinals shift by one from residue 3 onwards.
* **Chain L/102** carries an altloc pair. Two conformers must count as one
  residue, not two.
* **Chain M repeats entity 1** (a homodimer copy of chain H) and is listed
  *after* entity 2, and its residues are listed out of `label_seq_id` order.
  Both give Mol* a reason to reorder atoms on load — it buckets `atom_site` by
  `label_entity_id`, then `label_asym_id`, then sorts by `label_seq_id` — while
  BioPython reads strictly in file order. The residue ordinal must follow file
  order on both sides, which is what `residueSourceIndex` is for.
* **No chain's `auth_asym_id` equals its `label_asym_id`.** The author names
  the chains H, L and M; the mmCIF labels them A, B and C, exactly as RCSB
  assigns `label_asym_id` in deposition order regardless of author naming.
  Reading the label instead of the author id renames every chain, so every
  residue key the sequence panel emits stops resolving.
* **The ligand and waters** get their own `label_asym_id` (D, E, F) while
  keeping the polymer's `auth_asym_id`, as RCSB writes them. Grouping by
  `label_asym_id` would additionally invent chains the backend never reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent

# One backbone per residue is enough: the parsers segment on residue identity,
# not on atom completeness, and small files stay reviewable in a diff.
BACKBONE: list[tuple[str, str, str]] = [
    ("N", "N", " "),
    ("CA", "C", " "),
    ("C", "C", " "),
    ("O", "O", " "),
]


@dataclass(frozen=True)
class Res:
    """One residue, in the order it appears in the file."""

    group: str  # ATOM | HETATM
    resname: str
    auth_asym: str
    label_asym: str
    entity: str
    auth_seq: int
    label_seq: str = "."
    icode: str = " "
    atoms: tuple[tuple[str, str, str], ...] = tuple(BACKBONE)


def _poly(
    auth: str, label: str, entity: str, rows: list[tuple[str, int, str, str]]
) -> list[Res]:
    """rows: (resname, auth_seq, label_seq, icode)."""
    return [
        Res(
            group="HETATM" if name == "MSE" else "ATOM",
            resname=name,
            auth_asym=auth,
            label_asym=label,
            entity=entity,
            auth_seq=seq,
            label_seq=lseq,
            icode=icode,
        )
        for (name, seq, lseq, icode) in rows
    ]


# Chain H: entity 1, non-1-based, gapped, insertion code, MSE inside the polymer.
CHAIN_H = _poly(
    "H", "A", "1",
    [
        ("THR", 27, "1", " "),
        ("ALA", 28, "2", " "),
        ("MSE", 29, "3", " "),   # HETATM inside the polymer — skipped by both
        ("GLY", 34, "4", " "),   # gap: 30-33 unmodelled
        ("SER", 34, "5", "A"),   # insertion code; auth_seq repeats
        ("LYS", 35, "6", " "),
    ],
)

# Chain L: entity 2, with an altloc pair on CYS 102.
_CYS_ALTLOC = tuple(
    [(n, e, "A") for (n, e, _) in BACKBONE] + [("SG", "S", "A"), ("SG", "S", "B")]
)
CHAIN_L = [
    Res("ATOM", "VAL", "L", "B", "2", 101, "1"),
    Res("ATOM", "CYS", "L", "B", "2", 102, "2", atoms=_CYS_ALTLOC),
    Res("ATOM", "TRP", "L", "B", "2", 103, "3"),
    Res("ATOM", "PRO", "L", "B", "2", 104, "4"),
]

# Chain M: a second copy of entity 1, written after entity 2 AND out of
# label_seq_id order. Mol* reorders it twice over; file order must still win.
CHAIN_M = _poly(
    "M", "C", "1",
    [
        ("GLY", 34, "4", " "),
        ("THR", 27, "1", " "),
        ("ALA", 28, "2", " "),
        ("MSE", 29, "3", " "),
        ("SER", 34, "5", "A"),
        ("LYS", 35, "6", " "),
    ],
)

# Ligand and waters: own label_asym_id, polymer's auth_asym_id.
SOLVENT = [
    Res("HETATM", "HEM", "H", "D", "4", 201, atoms=(("FE", "FE", " "),)),
    Res("HETATM", "HOH", "H", "E", "5", 301, atoms=(("O", "O", " "),)),
    Res("HETATM", "HOH", "M", "F", "5", 301, atoms=(("O", "O", " "),)),
]

RESIDUES: list[Res] = CHAIN_H + CHAIN_L + CHAIN_M + SOLVENT

# Coordinates carry no meaning here, so each atom gets a distinct ascending
# value. Identical in both files, which keeps the pair diffable.
def _coords() -> list[float]:
    return [float(i + 1) for i in range(sum(len(r.atoms) for r in RESIDUES))]


PDB_HEADER = [
    "HEADER    PARITY TEST                             01-JAN-00   9XYZ",
    "TITLE     SYNTHETIC PDB/MMCIF PARSER PARITY FIXTURE",
    "COMPND    MOL_ID: 1;",
    "COMPND   2 MOLECULE: PARITY TEST CONSTRUCT;",
    "COMPND   3 CHAIN: H, L, M",
    "SOURCE    MOL_ID: 1;",
    "SOURCE   2 ORGANISM_SCIENTIFIC: SYNTHETIC CONSTRUCT",
]


def write_pdb(path: Path) -> None:
    lines = list(PDB_HEADER)
    coords = _coords()
    serial = 1
    for res in RESIDUES:
        for name, element, altloc in res.atoms:
            v = coords[serial - 1]
            atom_name = f" {name:<3}" if len(name) < 4 else name
            lines.append(
                f"{res.group:<6}{serial:>5} {atom_name}{altloc}"
                f"{res.resname:>3} {res.auth_asym}{res.auth_seq:>4}{res.icode}   "
                f"{v:>8.3f}{v:>8.3f}{v:>8.3f}{1.00:>6.2f}{10.00:>6.2f}"
                f"          {element:>2}"
            )
            serial += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


CIF_COLUMNS = [
    "group_PDB", "id", "type_symbol", "label_atom_id", "label_alt_id",
    "label_comp_id", "label_asym_id", "label_entity_id", "label_seq_id",
    "pdbx_PDB_ins_code", "Cartn_x", "Cartn_y", "Cartn_z", "occupancy",
    "B_iso_or_equiv", "auth_seq_id", "auth_comp_id", "auth_asym_id",
    "auth_atom_id", "pdbx_PDB_model_num",
]


def write_cif(path: Path) -> None:
    out = [
        "data_9XYZ",
        "#",
        "_entry.id   9XYZ",
        "#",
        "_struct.title   'Synthetic PDB/mmCIF parser parity fixture'",
        "#",
        "loop_",
        *(f"_atom_site.{column}" for column in CIF_COLUMNS),
    ]
    coords = _coords()
    serial = 1
    for res in RESIDUES:
        for name, element, altloc in res.atoms:
            v = coords[serial - 1]
            row = {
                "group_PDB": res.group,
                "id": str(serial),
                "type_symbol": element,
                "label_atom_id": name,
                "label_alt_id": "." if altloc == " " else altloc,
                "label_comp_id": res.resname,
                "label_asym_id": res.label_asym,
                "label_entity_id": res.entity,
                "label_seq_id": res.label_seq,
                "pdbx_PDB_ins_code": "?" if res.icode == " " else res.icode,
                "Cartn_x": f"{v:.3f}",
                "Cartn_y": f"{v:.3f}",
                "Cartn_z": f"{v:.3f}",
                "occupancy": "1.00",
                "B_iso_or_equiv": "10.00",
                "auth_seq_id": str(res.auth_seq),
                "auth_comp_id": res.resname,
                "auth_asym_id": res.auth_asym,
                "auth_atom_id": name,
                "pdbx_PDB_model_num": "1",
            }
            out.append(" ".join(row[column] for column in CIF_COLUMNS))
            serial += 1
    out.append("#")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_pdb(FIXTURES / "parity_multichain.pdb")
    write_cif(FIXTURES / "parity_multichain.cif")
    print(f"wrote parity_multichain.pdb / .cif to {FIXTURES}")
