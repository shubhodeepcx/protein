from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from Bio.PDB import MMCIFParser, PDBParser
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
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


def to_one_letter(resname: str) -> tuple[str, bool]:
    """Return (one_letter, is_standard). Unknown residues -> ('X', False).

    Public because A5 (`services/functional.py`) has to re-derive each chain's
    sequence from the same structure in order to attach an `auth_seq_id` to
    every ordinal, and then check that what it derived is byte-for-byte what
    `parse()` returned. Two copies of this table would make that check
    tautological against the wrong alphabet.
    """
    code = _AA_THREE_TO_ONE.get(resname.upper())
    if code is None:
        return "X", False
    return code, True


# Nucleotide residue names as the PDB writes them inside a polymer chain:
# deoxyribonucleotides (DA..DU, DI) and ribonucleotides (A, C, G, U, I), plus
# the unknown-nucleotide placeholder N. Public for the same reason as
# `to_one_letter`: `services/functional.py` and `services/compounds.py` have to
# drop exactly the chains `parse()` drops.
NUCLEOTIDE_ONE_LETTER: dict[str, str] = {
    "DA": "A", "DC": "C", "DG": "G", "DT": "T", "DU": "U", "DI": "I", "DN": "N",
    "A": "A", "C": "C", "G": "G", "U": "U", "I": "I", "N": "N",
}


def is_nucleic_acid_chain(resnames: Sequence[str]) -> bool:
    """True when every polymer residue in a chain is a nucleotide.

    The rule is deliberately "every", not "most": a chain carrying even one
    amino acid stays a protein chain exactly as before, so ordinals in mixed or
    unusual chains (poly-UNK cryo-EM models, a peptide-nucleic-acid hybrid) do
    not move. Only a pure DNA/RNA strand is taken out of the protein chains,
    where it used to arrive as a run of `X` and be analysed as protein.
    """
    return bool(resnames) and all(
        name.strip().upper() in NUCLEOTIDE_ONE_LETTER for name in resnames
    )


def _detect_format(path: Path) -> Literal["pdb", "mmcif"]:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"cif", "mmcif"}:
        return "mmcif"
    return "pdb"


# mmCIF source categories that carry the organism, most authoritative first.
#
# BioPython's `MMCIFParser` builds its `structure.header` from six keys only —
# name, head, idcode, deposition_date, structure_method, resolution — and has no
# `source` entry at all, so `_extract_header_strings` can never find an organism
# in an mmCIF. Every RCSB import is an mmCIF (`rcsb.download_structure` fetches
# `.cif`), which is why the viewer showed "Organism: Unknown" seconds after the
# search card showed the organism correctly. The value has to come from the raw
# category dict instead.
_MMCIF_ORGANISM_KEYS: tuple[str, ...] = (
    # Recombinant expression — the gene's source organism. This is what RCSB's
    # own `rcsb_entity_source_organism.scientific_name` is derived from.
    "_entity_src_gen.pdbx_gene_src_scientific_name",
    # Isolated from a natural source (what real 1CRN carries).
    "_entity_src_nat.pdbx_organism_scientific",
    # Synthetic construct.
    "_pdbx_entity_src_syn.organism_scientific",
    # AlphaFold / ModelArchive predicted models.
    "_ma_target_ref_db_details.organism_scientific",
)

# mmCIF spells "no value" as `?` and "not applicable" as `.`; MMCIF2Dict hands
# both through verbatim, so they must not be mistaken for an organism name.
_MMCIF_NULL_TOKENS = frozenset({"?", "."})

# How several organisms are rendered into the single `ProteinSummary.organism`
# string. A multi-entity mmCIF (a complex, or an assembly) names one organism per
# entity, and taking only the first one reports a chimeric structure as if it
# came from a single species.
_MMCIF_ORGANISM_JOINER = ", "

# Budget for the joined names, in characters. The guard is on the *rendered
# length* rather than on a count of names, because that is the actual symptom:
# `organism` is one line in the UI, and one line is a width, not a number of
# entities. So three long names and eight short ones are both allowed to fill
# it. Whatever does not fit is counted into a trailing "and N more" — the line
# stays short, but it never claims to be the whole list when it is not.
_MMCIF_ORGANISM_MAX_CHARS = 120


def _collect_mmcif_organisms(mmcif_dict: dict[str, object]) -> list[str]:
    """Every distinct organism named by the mmCIF source categories, in order.

    Deduplicated case-insensitively (an entry may spell the same species
    differently in two categories); the first spelling seen is the one kept.
    Empty when the file names no organism at all.
    """
    seen: set[str] = set()
    names: list[str] = []
    for key in _MMCIF_ORGANISM_KEYS:
        raw = mmcif_dict.get(key)
        if raw is None:
            continue
        # MMCIF2Dict returns a list per key: one element per row of a looped
        # category — which is one row per entity, the multi-organism case — and
        # still a one-element list for a single-row category. Be tolerant of a
        # bare string so a hand-written fixture cannot silently read as empty.
        values = [raw] if isinstance(raw, str) else list(raw)  # type: ignore[arg-type]
        for value in values:
            if not isinstance(value, str):
                continue
            cleaned = value.strip()
            if not cleaned or cleaned in _MMCIF_NULL_TOKENS:
                continue
            fingerprint = cleaned.casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            names.append(cleaned)
    return names


def _join_organisms(names: Sequence[str]) -> str | None:
    """Render distinct organism names as one line, or None when there are none.

    A single name renders as exactly itself — no separator, no suffix — so a
    single-organism entry is unchanged. Several are joined in first-seen order
    until the line would exceed `_MMCIF_ORGANISM_MAX_CHARS`; the rest are
    reported as a trailing "and N more" so a capped line says that it is capped
    instead of silently dropping entities. The first name is always kept whole,
    even if it alone is over budget: truncating a species name would invent one.
    """
    if not names:
        return None

    kept: list[str] = [names[0]]
    length = len(names[0])
    for name in names[1:]:
        grown = length + len(_MMCIF_ORGANISM_JOINER) + len(name)
        if grown > _MMCIF_ORGANISM_MAX_CHARS:
            break
        kept.append(name)
        length = grown

    joined = _MMCIF_ORGANISM_JOINER.join(kept)
    remaining = len(names) - len(kept)
    if remaining:
        joined = f"{joined} and {remaining} more"
    return joined


def _extract_mmcif_organism(mmcif_dict: dict[str, object]) -> str | None:
    """Every distinct organism the mmCIF names, as one line, else None."""
    return _join_organisms(_collect_mmcif_organisms(mmcif_dict))


def _mmcif_dict_for(struct_parser: MMCIFParser, path: Path) -> dict[str, object]:
    """The category dict `MMCIFParser` already built, re-reading only if absent.

    `get_structure` stores the parsed dict on the parser, so the common path
    costs nothing. The fallback keeps this correct if BioPython ever stops
    exposing it, at the price of one extra read.
    """
    existing = getattr(struct_parser, "_mmcif_dict", None)
    if isinstance(existing, dict) and existing:
        return existing
    return MMCIF2Dict(str(path))


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


def parse(
    path: Path | str,
    uid: str,
    source: Literal["uploaded", "rcsb", "alphafold", "uniprot"] = "uploaded",
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

    nucleic_acid_chains: list[str] = []

    for chain in model.get_chains():
        polymer = [r for r in chain.get_residues() if r.id[0] == " "]
        if is_nucleic_acid_chain([r.get_resname() for r in polymer]):
            # A DNA/RNA strand is a compound bound to the protein, not protein:
            # it is reported by `/compounds`, never fed to protein analytics.
            nucleic_acid_chains.append(chain.id)
            continue

        seq_chars: list[str] = []
        for residue in polymer:
            # residue.id is (hetero_flag, seq_id, icode). Hetero flag != " "
            # marks waters, ligands, and other non-polymer entries, which the
            # `polymer` filter above has already dropped.
            one, is_std = to_one_letter(residue.get_resname())
            if not is_std:
                nonstandard_seen.add(residue.get_resname().upper())
            seq_chars.append(one)
            for _atom in residue.get_atoms():
                atom_count += 1

        seq = "".join(seq_chars)
        if not seq:
            # Skip chains with no polymer residues at all (ligand- or water-only).
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
    if nucleic_acid_chains:
        warnings.append(
            "Nucleic-acid chains reported as compounds, not protein: "
            + ", ".join(nucleic_acid_chains)
        )

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

    name, organism = _extract_header_strings(structure)
    if fmt == "mmcif" and organism is None:
        organism = _extract_mmcif_organism(_mmcif_dict_for(struct_parser, p))

    # pLDDT heuristic: trust the header over B-factor pattern.
    # B-factor range alone is not reliable for distinguishing AlphaFold from X-ray.
    header = getattr(structure, "header", None) or {}
    header_str = str(header).upper()
    has_plddt = "ALPHAFOLD" in header_str or (
        # Explicit when the file itself came from AlphaFold DB, or from a
        # UniProt import — UniProt has no coordinates of its own, so a
        # UniProt import downloads the cross-referenced AlphaFold model.
        source in ("alphafold", "uniprot")
    )

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
        nucleic_acid_chains=nucleic_acid_chains,
    )
