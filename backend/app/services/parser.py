from __future__ import annotations

from pathlib import Path
from typing import Literal

from Bio.PDB import MMCIFParser, PDBParser
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from app.models.protein import ChainInfo, ProteinSummary

# Standard amino-acid 3-letter -> 1-letter mapping.
# BioPython removed `three_to_one` in 1.80+, so we maintain the mapping here.
_AA_THREE_TO_ONE: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _to_one_letter(resname: str) -> tuple[str, bool]:
    """Return (one_letter, is_standard). Unknown residues -> ('X', False)."""
    code = _AA_THREE_TO_ONE.get(resname.upper())
    if code is None:
        return "X", False
    return code, True


def _detect_format(path: Path) -> Literal["pdb", "mmcif"]:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"cif", "mmcif"}:
        return "mmcif"
    return "pdb"


def _extract_header_strings(structure) -> tuple[str | None, str | None]:
    """Pull (name, organism) from PDB header dict when available."""
    header = getattr(structure, "header", None) or {}
    name: str | None = None
    organism: str | None = None

    raw_name = header.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        name = raw_name.strip()

    compound = header.get("compound")
    if name is None and isinstance(compound, dict):
        first = compound.get("1") if "1" in compound else next(iter(compound.values()), None)
        if isinstance(first, dict):
            mol = first.get("molecule")
            if isinstance(mol, str) and mol.strip():
                name = mol.strip()

    source = header.get("source")
    if isinstance(source, dict):
        first = source.get("1") if "1" in source else next(iter(source.values()), None)
        if isinstance(first, dict):
            org = first.get("organism_scientific")
            if isinstance(org, str) and org.strip():
                organism = org.strip()

    return name, organism


async def parse(
    path: Path | str,
    uid: str,
    source: Literal["uploaded", "rcsb", "alphafold"] = "uploaded",
    source_id: str | None = None,
) -> ProteinSummary:
    """Parse a PDB or mmCIF file into a ProteinSummary.

    Contract: returns a valid ProteinSummary for any well-formed structure file.
    Non-fatal issues (non-standard residues, missing chains) accumulate in
    `warnings`; fatal parse errors propagate as exceptions for the caller to
    surface as HTTP 400s.
    """
    p = Path(path)
    fmt = _detect_format(p)
    warnings: list[str] = []

    if fmt == "mmcif":
        struct_parser = MMCIFParser(QUIET=True)
    else:
        struct_parser = PDBParser(QUIET=True)
    structure = struct_parser.get_structure(uid, str(p))

    chains: list[ChainInfo] = []
    atom_count = 0
    b_factors: list[float] = []
    nonstandard_seen: set[str] = set()

    # Take the first model (most PDB files have only model 1; AlphaFold likewise).
    try:
        model = next(structure.get_models())
    except StopIteration:
        return ProteinSummary(
            id=uid,
            source=source,
            source_id=source_id,
            name=None,
            organism=None,
            file_url=f"/api/proteins/{uid}/file",
            file_format=fmt,
            chains=[],
            residue_count=0,
            atom_count=0,
            molecular_weight=0.0,
            has_plddt=False,
            warnings=["Structure contains no models"],
        )

    for chain in model.get_chains():
        seq_chars: list[str] = []
        for residue in chain.get_residues():
            # residue.id is (hetero_flag, seq_id, icode). Hetero flag != " "
            # marks waters, ligands, and other non-polymer entries.
            if residue.id[0] != " ":
                continue
            one, is_std = _to_one_letter(residue.get_resname())
            if not is_std:
                nonstandard_seen.add(residue.get_resname().upper())
            seq_chars.append(one)
            for atom in residue.get_atoms():
                atom_count += 1
                b = atom.get_bfactor()
                if 0 < b <= 100:
                    b_factors.append(b)

        seq = "".join(seq_chars)
        if not seq:
            # Skip chains with no standard residues (e.g., DNA-only or ligand-only chains).
            continue
        chains.append(
            ChainInfo(
                id=f"{uid}:{chain.id}",
                label=chain.id,
                sequence=seq,
                residue_count=len(seq),
            )
        )

    if not chains:
        warnings.append("No standard amino-acid chains found in structure")

    if nonstandard_seen:
        warnings.append(
            "Non-standard residues replaced with 'X': "
            + ", ".join(sorted(nonstandard_seen))
        )

    residue_count = sum(c.residue_count for c in chains)

    # Molecular weight: sum per-chain ProtParam molecular_weight.
    # Strip the placeholder 'X' before passing to ProtParam (it raises on unknowns).
    mw = 0.0
    for ch in chains:
        clean_seq = ch.sequence.replace("X", "")
        if not clean_seq:
            continue
        try:
            mw += ProteinAnalysis(clean_seq).molecular_weight()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"MW failed for chain {ch.label}: {exc}")

    # pLDDT heuristic: AlphaFold writes per-atom confidence in the B-factor column,
    # always within (0, 100]. Require at least ~10 atoms before deciding.
    has_plddt = len(b_factors) >= 10 and atom_count > 0 and len(b_factors) == atom_count

    name, organism = _extract_header_strings(structure)

    return ProteinSummary(
        id=uid,
        source=source,
        source_id=source_id,
        name=name,
        organism=organism,
        file_url=f"/api/proteins/{uid}/file",
        file_format=fmt,
        chains=chains,
        residue_count=residue_count,
        atom_count=atom_count,
        molecular_weight=mw,
        has_plddt=has_plddt,
        warnings=warnings,
    )
