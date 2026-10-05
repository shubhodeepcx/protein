"""Compounds: everything in a structure file that is related to the protein
but is not the protein itself.

`ProteinSummary.chains` is protein-only on purpose, so composition,
hydrophobicity and every other analytic describe the protein. This module
describes the rest of the file:

* **Nucleic-acid chains**: DNA or RNA strands, with base composition, GC
  content and the protein residues that touch them (the DNA/RNA-binding
  interface).
* **Hetero groups**, one `CompoundGroup` per chemical component, classified as
  an ion, carbohydrate, cofactor/nucleotide, free amino acid, modified residue,
  crystallisation additive, or (everything else) a ligand.
* **Waters**, counted but not listed.

Everything here is an observation of the coordinates in front of us. Names and
formulas come from the file's own HETNAM/FORMUL records or `_chem_comp`
category, with a small built-in table for files that carry neither. Contacts are
measured heavy-atom distances, the same rule and cutoff as A5's bound ligands.

The one judgement call is **in-chain versus free**. RCSB writes
selenomethionine and phosphoserine as HETATM records inside a protein chain.
A5 told them apart from a free amino acid by the presence of an N/CA/C
backbone, which also hid a genuine free amino acid. Here the test is the
peptide bond itself: a hetero amino acid whose N or C is within bonding
distance of a neighbouring residue's C or N is part of the chain; one that is
not is a free amino acid.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from Bio.PDB import NeighborSearch

from app.models.compounds import (
    CompoundCategory,
    CompoundGroup,
    CompoundInstance,
    CompoundsResponse,
    NucleicAcidChain,
    NucleicAcidKind,
)
from app.models.functional import LigandContact
from app.models.protein import ProteinSummary
from app.services.external import as_int
from app.services.functional import (
    CONTACT_CUTOFF_ANGSTROMS,
    WATER_NAMES,
    ChainResidues,
    read_chain_residues,
)
from app.services.parser import NUCLEOTIDE_ONE_LETTER, to_one_letter

logger = logging.getLogger(__name__)

#: A peptide C-N bond is ~1.33 A. 1.75 A admits a poorly refined bond and
#: rejects any non-bonded contact (the closest of which are ~2.5 A).
PEPTIDE_BOND_MAX_ANGSTROMS = 1.75

# Order the UI lists categories in: the biologically meaningful partners first,
# crystallisation leftovers last.
CATEGORY_ORDER: tuple[CompoundCategory, ...] = (
    "ligand",
    "cofactor",
    "ion",
    "carbohydrate",
    "free_amino_acid",
    "modified_residue",
    "additive",
)

# ------------------------------------------------------------ reference tables
#
# Small and deliberately conservative: a code missing from every table falls
# through to "ligand", which is the honest default for "a molecule bound to the
# protein". `_chem_comp.type` from an mmCIF overrides these where it is decisive.

METAL_AND_HALIDE_ELEMENTS = frozenset(
    {
        "LI", "NA", "K", "RB", "CS", "MG", "CA", "SR", "BA", "MN", "FE", "CO",
        "NI", "CU", "ZN", "CD", "HG", "PT", "AU", "AG", "PB", "AL", "GA", "MO",
        "W", "V", "CR", "TL", "YB", "SM", "GD", "TB", "EU", "LU", "HO", "PD",
        "IR", "OS", "RU", "RH", "CL", "BR", "I", "F",
    }
)

ION_CODES: dict[str, str] = {
    "ZN": "Zinc ion", "MG": "Magnesium ion", "CA": "Calcium ion", "NA": "Sodium ion",
    "K": "Potassium ion", "CL": "Chloride ion", "MN": "Manganese(II) ion",
    "FE": "Fe(III) ion", "FE2": "Fe(II) ion", "CU": "Copper(II) ion", "CU1": "Copper(I) ion",
    "CO": "Cobalt(II) ion", "NI": "Nickel(II) ion", "CD": "Cadmium ion",
    "HG": "Mercury(II) ion", "BR": "Bromide ion", "IOD": "Iodide ion", "F": "Fluoride ion",
    "SR": "Strontium ion", "BA": "Barium(II) ion", "CS": "Cesium ion", "LI": "Lithium ion",
    "RB": "Rubidium ion", "PT": "Platinum(II) ion", "AU": "Gold ion", "PB": "Lead(II) ion",
    "YB": "Ytterbium(III) ion", "GD": "Gadolinium ion", "SM": "Samarium(III) ion",
    "MO": "Molybdenum ion", "W": "Tungsten ion",
}

CARBOHYDRATE_CODES: dict[str, str] = {
    "NAG": "N-acetyl-beta-D-glucosamine", "NDG": "N-acetyl-alpha-D-glucosamine",
    "MAN": "alpha-D-mannopyranose", "BMA": "beta-D-mannopyranose",
    "FUC": "alpha-L-fucopyranose", "FUL": "beta-L-fucopyranose",
    "GAL": "beta-D-galactopyranose", "GLA": "alpha-D-galactopyranose",
    "GLC": "alpha-D-glucopyranose", "BGC": "beta-D-glucopyranose",
    "SIA": "N-acetyl-alpha-neuraminic acid", "XYS": "alpha-D-xylopyranose",
    "XYP": "beta-D-xylopyranose", "NGA": "N-acetyl-D-galactosamine",
    "A2G": "N-acetyl-alpha-D-galactosamine", "FRU": "beta-D-fructofuranose",
    "SUC": "sucrose", "MAL": "maltose", "TRE": "trehalose", "LAT": "beta-lactose",
    "RIB": "alpha-D-ribofuranose", "GCU": "alpha-D-glucopyranuronic acid",
    "IDS": "2-O-sulfo-alpha-L-idopyranuronic acid", "SGN": "N,6-O-disulfo-glucosamine",
}

COFACTOR_CODES: dict[str, str] = {
    "HEM": "Protoporphyrin IX containing Fe (heme)", "HEC": "Heme C",
    "HEA": "Heme A", "FAD": "Flavin-adenine dinucleotide", "FMN": "Flavin mononucleotide",
    "NAD": "Nicotinamide-adenine dinucleotide", "NAI": "NADH",
    "NAP": "NADP nicotinamide-adenine-dinucleotide phosphate", "NDP": "NADPH",
    "ATP": "Adenosine-5'-triphosphate", "ADP": "Adenosine-5'-diphosphate",
    "AMP": "Adenosine monophosphate", "ANP": "AMP-PNP (non-hydrolysable ATP analogue)",
    "ACP": "AMP-PCP (non-hydrolysable ATP analogue)", "AGS": "ATP-gamma-S",
    "GTP": "Guanosine-5'-triphosphate", "GDP": "Guanosine-5'-diphosphate",
    "GNP": "GMP-PNP (non-hydrolysable GTP analogue)", "GSP": "GTP-gamma-S",
    "CTP": "Cytidine-5'-triphosphate", "UTP": "Uridine 5'-triphosphate",
    "UDP": "Uridine-5'-diphosphate", "COA": "Coenzyme A", "ACO": "Acetyl coenzyme A",
    "SAM": "S-adenosylmethionine", "SAH": "S-adenosyl-L-homocysteine",
    "PLP": "Pyridoxal-5'-phosphate", "TPP": "Thiamine diphosphate", "BTN": "Biotin",
    "CLA": "Chlorophyll A", "BCL": "Bacteriochlorophyll A", "SF4": "Iron/sulfur cluster [4Fe-4S]",
    "FES": "Fe2/S2 (inorganic) cluster", "F3S": "Fe3-S4 cluster", "PQQ": "Pyrroloquinoline quinone",
    "H4B": "Tetrahydrobiopterin", "MTE": "Molybdopterin", "B12": "Cobalamin",
    "CNC": "Cyanocobalamin", "GSH": "Glutathione", "LPA": "Lipoic acid",
    "UQ1": "Ubiquinone-1", "MQ7": "Menaquinone-7", "RET": "Retinal",
}

ADDITIVE_CODES: dict[str, str] = {
    "SO4": "Sulfate ion", "PO4": "Phosphate ion", "GOL": "Glycerol", "EDO": "1,2-ethanediol",
    "PEG": "Di(hydroxyethyl)ether", "PG4": "Tetraethylene glycol", "1PE": "Pentaethylene glycol",
    "P6G": "Hexaethylene glycol", "PGE": "Triethylene glycol", "ACT": "Acetate ion",
    "ACY": "Acetic acid", "MPD": "(4S)-2-methyl-2,4-pentanediol", "DMS": "Dimethyl sulfoxide",
    "FMT": "Formic acid", "TRS": "Tris buffer", "CIT": "Citric acid", "FLC": "Citrate anion",
    "EPE": "HEPES", "MES": "MES buffer", "BME": "Beta-mercaptoethanol", "IMD": "Imidazole",
    "NO3": "Nitrate ion", "SCN": "Thiocyanate ion", "IPA": "Isopropyl alcohol",
    "EOH": "Ethanol", "MOH": "Methanol", "BOG": "Octyl beta-D-glucopyranoside (detergent)",
    "LDA": "Lauryl dimethylamine-N-oxide (detergent)", "DTT": "Dithiothreitol",
    "TLA": "L(+)-tartaric acid", "MLI": "Malonate ion", "AZI": "Azide ion", "NH4": "Ammonium ion",
    "CAC": "Cacodylate ion", "BU3": "(R,R)-2,3-butanediol", "PGO": "S-1,2-propanediol",
}

# Modified amino acids and the standard residue each derives from. Used for the
# `parent_residue` field only; classification does not depend on it.
MODIFIED_PARENT: dict[str, str] = {
    "MSE": "M", "SEP": "S", "TPO": "T", "PTR": "Y", "HYP": "P", "MLY": "K", "M3L": "K",
    "MLZ": "K", "ALY": "K", "KCX": "K", "LLP": "K", "CSO": "C", "CSD": "C", "CSS": "C",
    "CME": "C", "OCS": "C", "SMC": "C", "CSX": "C", "PCA": "E", "CGU": "E", "FME": "M",
    "NEP": "H", "HIC": "H", "AGM": "R", "DAL": "A", "DLE": "L", "DVA": "V", "DPR": "P",
    "DSN": "S", "DTH": "T", "DTR": "W", "DTY": "Y", "DPN": "F", "DGL": "E", "DAS": "D",
    "DLY": "K", "DAR": "R", "DCY": "C", "DGN": "Q", "DSG": "N", "DHI": "H", "DIL": "I",
    "MED": "M", "TYS": "Y", "SAC": "S", "ABA": "A", "AIB": "A", "NLE": "L", "ORN": "K",
}

_FREE_AMINO_ACID_NAMES: dict[str, str] = {
    "ALA": "Alanine", "ARG": "Arginine", "ASN": "Asparagine", "ASP": "Aspartic acid",
    "CYS": "Cysteine", "GLN": "Glutamine", "GLU": "Glutamic acid", "GLY": "Glycine",
    "HIS": "Histidine", "ILE": "Isoleucine", "LEU": "Leucine", "LYS": "Lysine",
    "MET": "Methionine", "PHE": "Phenylalanine", "PRO": "Proline", "SER": "Serine",
    "THR": "Threonine", "TRP": "Tryptophan", "TYR": "Tyrosine", "VAL": "Valine",
}

_BUILTIN_NAMES: dict[str, str] = {
    **ION_CODES,
    **CARBOHYDRATE_CODES,
    **COFACTOR_CODES,
    **ADDITIVE_CODES,
    **_FREE_AMINO_ACID_NAMES,
}

_NOTES_CONTACTS = (
    "Contacts are protein residues with a heavy atom within {cutoff:g} Å of the "
    "compound, measured in this file. Click a contact to select it in 3D."
)
_NOTE_NOTHING = (
    "This structure contains no non-protein components other than water: no "
    "nucleic acid, ion, ligand, glycan or cofactor is present in the file."
)
_NOTE_ADDITIVES = (
    "Additives are common crystallisation, cryoprotectant or buffer components. They "
    "are listed for completeness and are usually not biological partners."
)
_NOTE_MODIFIED = (
    "Modified residues are part of the protein chain (peptide-bonded to their "
    "neighbours) but are written as HETATM records, so they are not in the one-letter "
    "sequence or its residue numbering."
)


# ------------------------------------------------------------ file metadata


@dataclass(frozen=True)
class ComponentInfo:
    """What the file itself declares about one chemical component."""

    name: str | None = None
    formula: str | None = None
    formula_weight: float | None = None
    chem_type: str | None = None


def read_component_info(path: Path) -> dict[str, ComponentInfo]:
    """Component names, formulas and types as the file declares them.

    PDB: HETNAM (with continuation lines) and FORMUL. mmCIF: `_chem_comp`.
    A file that declares nothing yields an empty dict and the built-in table
    takes over. Never raises on malformed metadata; it is optional.
    """
    try:
        if path.suffix.lower().lstrip(".") in ("cif", "mmcif"):
            return _mmcif_component_info(path)
        return _pdb_component_info(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        logger.info("Could not read component metadata from %s: %s", path.name, exc)
        return {}


def _pdb_component_info(path: Path) -> dict[str, ComponentInfo]:
    names: dict[str, str] = {}
    formulas: dict[str, str] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            record = line[:6]
            if record == "HETNAM":
                code = line[11:14].strip().upper()
                text = line[15:70].strip()
                if not code or not text:
                    continue
                previous = names.get(code)
                if previous is None:
                    names[code] = text
                else:
                    # A continuation line. HETNAM wraps mid-word on a hyphen.
                    joiner = "" if previous.endswith("-") else " "
                    names[code] = previous + joiner + text
            elif record == "FORMUL":
                code = line[12:15].strip().upper()
                text = line[18:70].strip().lstrip("*").strip()
                if code and text:
                    formulas[code] = (formulas[code] + " " + text) if code in formulas else text
            elif record in ("ATOM  ", "HETATM"):
                # Header records all precede the coordinates.
                break
    codes = set(names) | set(formulas)
    return {
        code: ComponentInfo(name=names.get(code), formula=_clean_formula(formulas.get(code)))
        for code in codes
    }


# "2(C8 H15 N O6)" -> "C8 H15 N O6": FORMUL prefixes a copy count.
_FORMUL_COUNT = re.compile(r"^\d+\((.*)\)$")


def _clean_formula(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    match = _FORMUL_COUNT.match(text)
    return (match.group(1) if match else text).strip() or None


def _mmcif_component_info(path: Path) -> dict[str, ComponentInfo]:
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict

    data = MMCIF2Dict(str(path))
    ids = _as_list(data.get("_chem_comp.id"))
    if not ids:
        return {}
    columns = {
        key: _as_list(data.get(f"_chem_comp.{key}"))
        for key in ("name", "formula", "formula_weight", "type")
    }

    def cell(key: str, index: int) -> str | None:
        values = columns[key]
        if index >= len(values):
            return None
        value = values[index].strip().strip('"').strip()
        return None if value in ("", "?", ".") else value

    out: dict[str, ComponentInfo] = {}
    for index, code in enumerate(ids):
        weight_text = cell("formula_weight", index)
        try:
            weight = float(weight_text) if weight_text else None
        except ValueError:
            weight = None
        out[code.strip().upper()] = ComponentInfo(
            name=cell("name", index),
            formula=cell("formula", index),
            formula_weight=weight,
            chem_type=cell("type", index),
        )
    return out


def _as_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    return [str(item) for item in raw]  # type: ignore[union-attr]


# ------------------------------------------------------------ classification


def classify(
    code: str,
    *,
    heavy_elements: list[str],
    in_polymer: bool,
    has_backbone: bool,
    chem_type: str | None,
) -> CompoundCategory:
    """Which category a hetero group belongs to. Pure; first matching rule wins."""
    code = code.upper()
    kind = (chem_type or "").lower()
    if in_polymer:
        return "modified_residue"
    if "saccharide" in kind or code in CARBOHYDRATE_CODES:
        return "carbohydrate"
    if code in ION_CODES or (
        len(heavy_elements) == 1 and heavy_elements[0] in METAL_AND_HALIDE_ELEMENTS
    ):
        return "ion"
    if code in COFACTOR_CODES:
        return "cofactor"
    if code in ADDITIVE_CODES:
        return "additive"
    if (
        code in _FREE_AMINO_ACID_NAMES
        or code in MODIFIED_PARENT
        or "peptide linking" in kind
        or has_backbone
    ):
        return "free_amino_acid"
    return "ligand"


# ------------------------------------------------------------ geometry


@dataclass
class _ProteinIndex:
    search: NeighborSearch | None
    owner: dict[int, tuple[str, int]]
    by_label: dict[str, ChainResidues]


def _heavy_atoms(residue) -> list:
    out = []
    for atom in residue.get_atoms():
        element = (getattr(atom, "element", "") or "").strip().upper()
        if element in ("H", "D"):
            continue
        if not element and atom.get_name().strip().startswith(("H", "D")):
            continue
        out.append(atom)
    return out


def _protein_index(model, chains: list[ChainResidues]) -> _ProteinIndex:
    by_label = {chain.label: chain for chain in chains}
    owner: dict[int, tuple[str, int]] = {}
    atoms: list = []
    for chain in model.get_chains():
        if chain.id not in by_label:
            continue
        ordinal = 0
        for residue in chain.get_residues():
            if residue.id[0] != " ":
                continue
            ordinal += 1
            for atom in _heavy_atoms(residue):
                owner[id(atom)] = (chain.id, ordinal)
                atoms.append(atom)
    return _ProteinIndex(NeighborSearch(atoms) if atoms else None, owner, by_label)


def _contacts(atoms: Iterable, index: _ProteinIndex, cutoff: float) -> list[LigandContact]:
    if index.search is None:
        return []
    closest: dict[tuple[str, int], float] = {}
    counts: dict[tuple[str, int], int] = {}
    for atom in atoms:
        for neighbour in index.search.search(atom.coord, cutoff):
            found = index.owner.get(id(neighbour))
            if found is None:
                continue
            distance = float(((atom.coord - neighbour.coord) ** 2).sum() ** 0.5)
            if distance < closest.get(found, float("inf")):
                closest[found] = distance
            counts[found] = counts.get(found, 0) + 1
    contacts = [
        LigandContact(
            **index.by_label[label].ref(ordinal).model_dump(),
            min_distance=round(distance, 2),
            atom_contacts=counts[(label, ordinal)],
        )
        for (label, ordinal), distance in closest.items()
    ]
    contacts.sort(key=lambda c: (c.min_distance, c.chain, c.ordinal))
    return contacts


def _peptide_linked(chain) -> set[int]:
    """`id()` of every hetero residue in `chain` that is peptide-bonded to a neighbour."""
    termini: list = []
    for residue in chain.get_residues():
        for name in ("N", "C"):
            if name in residue:
                termini.append(residue[name])
    if not termini:
        return set()
    search = NeighborSearch(termini)
    linked: set[int] = set()
    for residue in chain.get_residues():
        if residue.id[0] == " " or residue.id[0] == "W":
            continue
        # Only an amino acid can be peptide-bonded into the chain. Without this,
        # a covalently attached inhibitor with an atom named "C" or "N" would be
        # mistaken for part of the protein.
        if not all(name in residue for name in ("N", "CA", "C")):
            continue
        for own, partner in (("N", "C"), ("C", "N")):
            if own not in residue:
                continue
            for neighbour in search.search(residue[own].coord, PEPTIDE_BOND_MAX_ANGSTROMS):
                if neighbour.get_parent() is not residue and neighbour.get_id() == partner:
                    linked.add(id(residue))
                    break
            if id(residue) in linked:
                break
    return linked


# ------------------------------------------------------------ nucleic acids


def _nucleic_kind(resnames: list[str]) -> NucleicAcidKind:
    deoxy = sum(1 for name in resnames if name.startswith("D"))
    if deoxy == len(resnames):
        return "DNA"
    if deoxy == 0:
        return "RNA"
    return "DNA/RNA hybrid"


def _describe_nucleic_chain(chain, index: _ProteinIndex, cutoff: float) -> NucleicAcidChain:
    polymer = [r for r in chain.get_residues() if r.id[0] == " "]
    names = [r.get_resname().strip().upper() for r in polymer]
    sequence = "".join(NUCLEOTIDE_ONE_LETTER.get(name, "N") for name in names)
    composition: dict[str, int] = {}
    for base in sequence:
        composition[base] = composition.get(base, 0) + 1
    identified = sum(composition.get(base, 0) for base in "ACGTU")
    gc = composition.get("G", 0) + composition.get("C", 0)
    atoms = [atom for residue in polymer for atom in _heavy_atoms(residue)]
    return NucleicAcidChain(
        label=chain.id,
        kind=_nucleic_kind(names),
        sequence=sequence,
        length=len(sequence),
        gc_fraction=round(gc / identified, 4) if identified else None,
        composition=dict(sorted(composition.items())),
        contacts=_contacts(atoms, index, cutoff),
    )


# ------------------------------------------------------------ entry point


@dataclass
class _GroupDraft:
    code: str
    category: CompoundCategory
    instances: list[CompoundInstance] = field(default_factory=list)


def build_compounds(
    uid: str,
    summary: ProteinSummary,
    structure,
    components: dict[str, ComponentInfo] | None = None,
    *,
    cutoff: float = CONTACT_CUTOFF_ANGSTROMS,
) -> CompoundsResponse:
    """Describe every non-protein component of model 1 of `structure`."""
    components = components or {}
    empty = CompoundsResponse(protein_id=uid, contact_cutoff=cutoff)
    try:
        model = next(structure.get_models())
    except StopIteration:
        return empty

    chains = read_chain_residues(structure, summary)
    index = _protein_index(model, chains)
    nucleic_labels = set(summary.nucleic_acid_chains)

    nucleic_acids: list[NucleicAcidChain] = []
    drafts: dict[tuple[str, CompoundCategory], _GroupDraft] = {}
    water_count = 0

    for chain in model.get_chains():
        if chain.id in nucleic_labels:
            nucleic_acids.append(_describe_nucleic_chain(chain, index, cutoff))
        linked = _peptide_linked(chain)
        for residue in chain.get_residues():
            if residue.id[0] == " ":
                continue
            code = residue.get_resname().strip().upper()
            if residue.id[0] == "W" or code in WATER_NAMES:
                water_count += 1
                continue
            atoms = _heavy_atoms(residue)
            atom_names = {atom.get_name().strip().upper() for atom in atoms}
            in_polymer = id(residue) in linked
            category = classify(
                code,
                heavy_elements=[(a.element or "").strip().upper() for a in atoms],
                in_polymer=in_polymer,
                has_backbone={"N", "CA", "C"} <= atom_names,
                chem_type=components.get(code, ComponentInfo()).chem_type,
            )
            icode = residue.id[2]
            draft = drafts.setdefault((code, category), _GroupDraft(code, category))
            draft.instances.append(
                CompoundInstance(
                    chain=chain.id,
                    auth_seq_id=as_int(residue.id[1]),
                    insertion_code=icode.strip() or None if isinstance(icode, str) else None,
                    atom_count=len(atoms),
                    contacts=[] if in_polymer else _contacts(atoms, index, cutoff),
                )
            )

    groups = [_finish_group(draft, components) for draft in drafts.values()]
    groups.sort(
        key=lambda g: (
            CATEGORY_ORDER.index(g.category),
            -max((len(i.contacts) for i in g.instances), default=0),
            g.code,
        )
    )
    return CompoundsResponse(
        protein_id=uid,
        contact_cutoff=cutoff,
        nucleic_acids=nucleic_acids,
        groups=groups,
        water_count=water_count,
        notes=_notes(groups, nucleic_acids, cutoff),
    )


def _finish_group(draft: _GroupDraft, components: dict[str, ComponentInfo]) -> CompoundGroup:
    info = components.get(draft.code, ComponentInfo())
    parent: str | None = None
    if draft.category in ("modified_residue", "free_amino_acid"):
        parent = MODIFIED_PARENT.get(draft.code)
        if parent is None:
            one, standard = to_one_letter(draft.code)
            parent = one if standard else None
    draft.instances.sort(key=lambda i: (-len(i.contacts), i.chain, i.auth_seq_id or 0))
    return CompoundGroup(
        code=draft.code,
        name=info.name or _BUILTIN_NAMES.get(draft.code),
        category=draft.category,
        formula=info.formula,
        formula_weight=info.formula_weight,
        parent_residue=parent,
        instances=draft.instances,
    )


def _notes(
    groups: list[CompoundGroup], nucleic_acids: list[NucleicAcidChain], cutoff: float
) -> list[str]:
    if not groups and not nucleic_acids:
        return [_NOTE_NOTHING]
    notes = [_NOTES_CONTACTS.format(cutoff=cutoff)]
    categories = {g.category for g in groups}
    if "additive" in categories:
        notes.append(_NOTE_ADDITIVES)
    if "modified_residue" in categories:
        notes.append(_NOTE_MODIFIED)
    return notes

