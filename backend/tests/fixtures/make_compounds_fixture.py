"""Generates `compounds_complex.pdb`, the fixture behind `tests/test_compounds.py`.

Run offline; the file it writes is committed:

    cd backend && python tests/fixtures/make_compounds_fixture.py

The protein is the first ten residues of 1CRN (the bundled demo structure),
so the backbone geometry is real. Everything else is placed relative to those
atoms so each case lands where it is meant to, and is far from the others:

* **SEP A/6**: residue 6 (SER) rewritten as HETATM phosphoserine with its
  backbone untouched, so it is still peptide-bonded to 5 and 7. It must be a
  *modified residue*, and chain A's ordinals must skip it (A:6 is ILE 7).
* **Chain B**: three DNA nucleotides (DG, DC, DA) 3.5 A from THR 2's CA, so
  it is a nucleic-acid chain with one GC-rich strand and a protein contact.
* **ZN A/101**: one atom 2.2 A from CYS 3's SG; an ion with a contact.
* **GLU A/102**: a complete free amino acid (N, CA, C, O, CB) 3.6 A from ILE
  7's CB, with no atom in peptide-bond range of anything. The case A5's
  backbone rule used to skip.
* **HEM A/103**: a three-atom stand-in 3.5 A from ALA 9's CB. A cofactor; its
  HETNAM name spans a continuation line.
* **SO4 A/104**: 30 A away from everything; an additive with no contacts.
* **LIG A/105**: an unknown two-atom code, also far away; falls through to
  *ligand* with no name.
* **HOH A/201, A/202**: waters, counted and never listed.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE.parent.parent / "app" / "static" / "1CRN.pdb"
OUT = HERE / "compounds_complex.pdb"


def _atom_line(
    record: str, serial: int, name: str, resname: str, chain: str, resseq: int,
    xyz: tuple[float, float, float], element: str,
) -> str:
    # PDB fixed columns: 4-char atom names start in column 13, shorter ones in 14.
    padded = name if len(name) == 4 else f" {name:<3}"
    x, y, z = xyz
    return (
        f"{record:<6}{serial:>5} {padded}{'':1}{resname:>3} {chain}{resseq:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{0.0:>6.2f}          {element:>2}"
    )


def _offset(xyz: tuple[float, float, float], dx: float, dy: float = 0.0, dz: float = 0.0):
    return (xyz[0] + dx, xyz[1] + dy, xyz[2] + dz)


def main() -> None:
    protein: list[tuple[str, str, int, tuple[float, float, float], str]] = []
    coords: dict[tuple[int, str], tuple[float, float, float]] = {}
    for line in SOURCE.read_text().splitlines():
        if not line.startswith("ATOM"):
            continue
        resseq = int(line[22:26])
        if resseq > 10:
            break
        name = line[12:16].strip()
        resname = line[17:20].strip()
        xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        element = line[76:78].strip() or name[0]
        protein.append((name, resname, resseq, xyz, element))
        coords[(resseq, name)] = xyz

    lines = [
        "HEADER    TEST FIXTURE: PROTEIN WITH BOUND COMPOUNDS",
        "HETNAM     SEP PHOSPHOSERINE",
        "HETNAM      ZN ZINC ION",
        "HETNAM     HEM PROTOPORPHYRIN IX CONTAINING FE (STAND-IN FOR A TEST,",
        "HETNAM   2 HEM THREE ATOMS ONLY)",
        "HETNAM     SO4 SULFATE ION",
        "FORMUL   2  ZN    ZN 2+",
        "FORMUL   3  HEM    C34 H32 FE N4 O4",
        "FORMUL   4  SO4    O4 S 2-",
        "FORMUL   5  HOH   *H2 O",
    ]
    serial = 0

    def emit(record, name, resname, chain, resseq, xyz, element):
        nonlocal serial
        serial += 1
        lines.append(_atom_line(record, serial, name, resname, chain, resseq, xyz, element))

    for name, resname, resseq, xyz, element in protein:
        if resseq == 6:
            emit("HETATM", name, "SEP", "A", resseq, xyz, element)
        else:
            emit("ATOM", name, resname, "A", resseq, xyz, element)
    # Phosphate on SEP's OG, so it is really a modified serine.
    emit("HETATM", "P", "SEP", "A", 6, _offset(coords[(6, "OG")], 1.6), "P")
    lines.append("TER")

    base = _offset(coords[(2, "CA")], 0.0, 3.5)
    for index, nucleotide in enumerate(("DG", "DC", "DA")):
        anchor = _offset(base, 0.0, 6.0 * index)
        emit("ATOM", "P", nucleotide, "B", index + 1, anchor, "P")
        emit("ATOM", "C1'", nucleotide, "B", index + 1, _offset(anchor, 0.0, 1.5), "C")
    lines.append("TER")

    emit("HETATM", "ZN", "ZN", "A", 101, _offset(coords[(3, "SG")], 2.2), "ZN")

    glu = _offset(coords[(7, "CB")], -3.6)
    for name, d, element in (
        ("CB", (0.0, 0.0, 0.0), "C"),
        ("CA", (-1.5, 0.0, 0.0), "C"),
        ("N", (-2.0, 1.4, 0.0), "N"),
        ("C", (-2.0, -1.4, 0.0), "C"),
        ("O", (-3.2, -1.6, 0.0), "O"),
    ):
        emit("HETATM", name, "GLU", "A", 102, _offset(glu, *d), element)

    hem = _offset(coords[(9, "CB")], 0.0, 0.0, 3.5)
    for name, d, element in (("FE", 0.0, "FE"), ("NA", 2.0, "N"), ("NB", -2.0, "N")):
        emit("HETATM", name, "HEM", "A", 103, _offset(hem, 0.0, d, 0.0), element)

    far = _offset(coords[(1, "N")], 30.0, 30.0, 30.0)
    emit("HETATM", "S", "SO4", "A", 104, far, "S")
    for i, d in enumerate(((1.5, 0, 0), (-1.5, 0, 0), (0, 1.5, 0), (0, -1.5, 0))):
        emit("HETATM", f"O{i + 1}", "SO4", "A", 104, _offset(far, *d), "O")

    other = _offset(far, 10.0)
    emit("HETATM", "C1", "LIG", "A", 105, other, "C")
    emit("HETATM", "C2", "LIG", "A", 105, _offset(other, 1.5), "C")

    emit("HETATM", "O", "HOH", "A", 201, _offset(far, -10.0), "O")
    emit("HETATM", "O", "HOH", "A", 202, _offset(far, -13.0), "O")
    lines.append("END")
    OUT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
