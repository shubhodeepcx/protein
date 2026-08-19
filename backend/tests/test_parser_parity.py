"""PDB/mmCIF parser parity for the residue ordinals P4's selection sync rides on.

## What this protects

P4 gave the sequence panel and the Mol* viewer a shared residue key,
`"<chain>:<1-based ordinal within that chain>"`. The ordinal is deliberately
NOT `auth_seq_id`. For the key to mean the same thing on both sides, three
things have to agree about which residues exist and in what order:

1. `app/services/parser.py`, which builds each chain's one-letter sequence;
2. `frontend/lib/molstar/residue-index.ts`, which mirrors that filter over
   Mol*'s atomic hierarchy (pinned separately in
   `frontend/lib/molstar/__tests__/residue-index.test.ts`);
3. the two BioPython parsers behind (1) — `PDBParser` and `MMCIFParser`.

(3) is what this module pins, and it is the piece P4 never exercised: P4 was
designed and tested entirely against PDB files. P5 then added RCSB import,
which downloads mmCIF and routes it to `MMCIFParser`. The two parsers can
differ in chain naming (`auth_asym_id` vs `label_asym_id`), in HETATM / MSE /
water / altloc handling, and in residue ordering. If they disagree, every
residue click on an imported RCSB structure lands on the wrong residue —
silently, and plausibly, because the neighbouring residue usually looks fine.

`tests/fixtures/make_parity_fixture.py` documents the fixture and every hazard
it encodes.

## Why the expected sequences are spelled out

Comparing the two parsers to each other is not enough on its own: a change that
moved BOTH parsers the same way — say, a filter that started keeping HETATM
polymer residues — would keep them equal and still shift every ordinal in the
UI. So the literal chain labels and sequences are pinned too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.parser import parse

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PDB_PATH = FIXTURES / "parity_multichain.pdb"
CIF_PATH = FIXTURES / "parity_multichain.cif"

# The ordinal convention, spelled out. Read these against the fixture:
#   H: THR 27, ALA 28, [MSE 29 skipped], GLY 34, SER 34A, LYS 35
#   L: VAL 101, CYS 102 (altloc A/B — one residue), TRP 103, PRO 104
#   M: file order GLY, THR, ALA, [MSE skipped], SER, LYS — NOT label_seq_id order
#
# The author names the chains H/L/M; the mmCIF labels them A/B/C, and gives the
# ligand and waters labels D/E/F while keeping their author chain. So the
# labels reported here must be H, L, M — never A, B, C, and never D, E, F.
EXPECTED_CHAINS: list[tuple[str, str]] = [
    ("H", "TAGSK"),
    ("L", "VCWP"),
    ("M", "GTASK"),
]


def _chains(path: Path) -> list[tuple[str, str]]:
    return [(c.label, c.sequence) for c in parse(path, uid="parity").chains]


@pytest.fixture(scope="module")
def pdb_chains() -> list[tuple[str, str]]:
    return _chains(PDB_PATH)


@pytest.fixture(scope="module")
def cif_chains() -> list[tuple[str, str]]:
    return _chains(CIF_PATH)


# --------------------------------------------------------------- the fixture

_PDB_ATOM_RE = re.compile(r"^(ATOM  |HETATM)")


def _pdb_atom_rows(text: str) -> list[tuple[str, ...]]:
    """(group, atom name, altloc, resname, chain, seq, icode) per ATOM record."""
    rows = []
    for line in text.splitlines():
        if not _PDB_ATOM_RE.match(line):
            continue
        rows.append(
            (
                line[0:6].strip(),
                line[12:16].strip(),
                line[16].strip(),
                line[17:20].strip(),
                line[21].strip(),
                line[22:26].strip(),
                line[26].strip(),
            )
        )
    return rows


def _cif_atom_rows(text: str) -> list[tuple[str, ...]]:
    """The same tuple, read out of the mmCIF `atom_site` loop."""
    lines = text.splitlines()
    columns = [
        line.strip().split(".", 1)[1]
        for line in lines
        if line.startswith("_atom_site.")
    ]
    rows = []
    for line in lines:
        if not line.startswith(("ATOM ", "HETATM ")):
            continue
        values = dict(zip(columns, line.split(), strict=True))
        rows.append(
            (
                values["group_PDB"],
                values["label_atom_id"],
                "" if values["label_alt_id"] == "." else values["label_alt_id"],
                values["label_comp_id"],
                values["auth_asym_id"],
                values["auth_seq_id"],
                ""
                if values["pdbx_PDB_ins_code"] in {"?", "."}
                else values["pdbx_PDB_ins_code"],
            )
        )
    return rows


def test_the_two_fixture_files_describe_the_same_structure() -> None:
    """Guards the guard.

    Everything below compares two files. That comparison only means something
    while the files hold the same atoms in the same order — otherwise a future
    edit to one of them could make the parity tests pass by making the inputs
    disagree. This asserts the premise directly, without going through either
    parser.
    """
    pdb_rows = _pdb_atom_rows(PDB_PATH.read_text(encoding="utf-8"))
    cif_rows = _cif_atom_rows(CIF_PATH.read_text(encoding="utf-8"))
    assert pdb_rows, "no ATOM/HETATM records found in the PDB fixture"
    assert pdb_rows == cif_rows


# --------------------------------------------------------------- the parity

def test_chain_labels_agree_across_formats(
    pdb_chains: list[tuple[str, str]], cif_chains: list[tuple[str, str]]
) -> None:
    """`MMCIFParser` must label chains by `auth_asym_id`, as `PDBParser` does.

    No chain in this fixture has `auth_asym_id == label_asym_id`, so falling
    back to the label renames all three (H/L/M -> A/B/C) and can invent chains
    D/E/F from the ligand and waters. The sequence panel would then render
    chains the viewer cannot resolve a click to.
    """
    assert [label for label, _ in cif_chains] == [label for label, _ in pdb_chains]
    assert [label for label, _ in cif_chains] == ["H", "L", "M"]


def test_residue_sequences_agree_across_formats(
    pdb_chains: list[tuple[str, str]], cif_chains: list[tuple[str, str]]
) -> None:
    """The load-bearing assertion: same residues, same order, per chain.

    Any difference here means residue N of a chain is a different residue
    depending on whether the structure was uploaded as PDB or imported from
    RCSB as mmCIF — and every click on an imported structure is off.
    """
    assert cif_chains == pdb_chains


@pytest.mark.parametrize("fmt", ["pdb", "cif"])
def test_ordinals_match_the_pinned_convention(
    fmt: str, pdb_chains: list[tuple[str, str]], cif_chains: list[tuple[str, str]]
) -> None:
    """Both formats, against the literal expected numbering.

    Pinned rather than derived, so a change that shifts both parsers in step
    still fails here.
    """
    assert (pdb_chains if fmt == "pdb" else cif_chains) == EXPECTED_CHAINS


@pytest.mark.parametrize("path", [PDB_PATH, CIF_PATH], ids=["pdb", "cif"])
def test_ordinal_is_not_auth_seq_id(path: Path) -> None:
    """The convention's whole point, restated as a test.

    Chain H is modelled from author residue 27 with a gap and an insertion
    code. If anything ever derives the ordinal from `auth_seq_id`, chain H
    reports 9 residues (27..35) instead of 5, and this fails.
    """
    chain_h = next(c for c in parse(path, uid="parity").chains if c.label == "H")
    assert chain_h.residue_count == 5
    assert chain_h.sequence == "TAGSK"


@pytest.mark.parametrize("path", [PDB_PATH, CIF_PATH], ids=["pdb", "cif"])
def test_hetatm_polymer_ligand_and_water_are_excluded(path: Path) -> None:
    """MSE, HEM and HOH are all `group_PDB = HETATM` and all must be skipped.

    MSE is the sharp one: it sits *inside* chain H's polymer, so keeping it
    would leave the chain plausible-looking while shifting every ordinal from
    position 3 onwards by one.
    """
    summary = parse(path, uid="parity")
    labels = {c.label for c in summary.chains}
    assert labels == {"H", "L", "M"}, "ligand/water label_asym_ids leaked in as chains"
    # MSE maps to the 'X' placeholder, so its absence is visible in the sequence.
    assert all("X" not in c.sequence for c in summary.chains)
    assert summary.warnings == []


@pytest.mark.parametrize("path", [PDB_PATH, CIF_PATH], ids=["pdb", "cif"])
def test_altloc_conformers_count_as_one_residue(path: Path) -> None:
    """CYS L/102 has A and B conformers; chain L is 4 residues, not 5."""
    chain_l = next(c for c in parse(path, uid="parity").chains if c.label == "L")
    assert chain_l.residue_count == 4
    assert chain_l.sequence == "VCWP"


@pytest.mark.parametrize("path", [PDB_PATH, CIF_PATH], ids=["pdb", "cif"])
def test_ordinals_follow_file_order_not_label_seq_id(path: Path) -> None:
    """Chain M lists its residues out of `label_seq_id` order on purpose.

    Mol* buckets `atom_site` by entity and asym id and then sorts by
    `label_seq_id`, so it sees chain M as THR-ALA-GLY-SER-LYS; BioPython reads
    the file as written. The ordinal is defined as file order, and the
    frontend undoes Mol*'s sort via `residueSourceIndex` to match. Sorting by
    `label_seq_id` here would yield "TAGSK" and break that agreement.
    """
    chain_m = next(c for c in parse(path, uid="parity").chains if c.label == "M")
    assert chain_m.sequence == "GTASK"


def test_format_is_reported_per_file() -> None:
    """`file_format` is what tells the frontend which Mol* parser to use."""
    assert parse(PDB_PATH, uid="parity").file_format == "pdb"
    assert parse(CIF_PATH, uid="parity").file_format == "mmcif"


def test_atom_and_residue_totals_agree_across_formats() -> None:
    """Weaker than the per-chain check, but it catches whole-chain drops."""
    pdb = parse(PDB_PATH, uid="parity")
    cif = parse(CIF_PATH, uid="parity")
    assert (cif.residue_count, cif.atom_count) == (pdb.residue_count, pdb.atom_count)
    assert cif.residue_count == 14
