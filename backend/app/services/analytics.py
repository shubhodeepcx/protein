from __future__ import annotations

from collections import Counter
from pathlib import Path

# Average residue masses (monoisotopic would be different; use average for MW
# reporting). Values are residue masses (NOT free amino acid masses), i.e. the
# amino-acid mass minus water. Source: Expasy ProtParam values.
_AA_AVG_MASS = {
    "A":  71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886, "C": 103.1388,
    "E": 129.1155, "Q": 128.1307, "G":  57.0519, "H": 137.1411, "I": 113.1594,
    "L": 113.1594, "K": 128.1741, "M": 131.1926, "F": 147.1766, "P":  97.1167,
    "S":  87.0782, "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V":  99.1326,
}
_WATER_MASS = 18.01528

# Kyte-Doolittle hydropathy scale
_KD_HYDROPATHY = {
    "A":  1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C":  2.5,
    "E": -3.5, "Q": -3.5, "G": -0.4, "H": -3.2, "I":  4.5,
    "L":  3.8, "K": -3.9, "M":  1.9, "F":  2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V":  4.2,
}

# Three-letter labels for display
_AA_THREE_LETTER = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys",
    "E": "Glu", "Q": "Gln", "G": "Gly", "H": "His", "I": "Ile",
    "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro",
    "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val",
}

_HYDROPHOBIC = set("AVILMFWY")
_POLAR = set("STNQ")  # uncharged polar
_CHARGED_POS = set("KRH")
_CHARGED_NEG = set("DE")
_AROMATIC = set("FWY")  # aromatic (overlaps with hydrophobic on purpose)
_CYSTEINE = set("C")

_AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"  # standard 20, alphabetical


def molecular_weight(sequence: str) -> float:
    """Sum of residue masses plus one water (for the chain terminus).

    Unknown 'X' residues are skipped. For 1CRN (TTCCPSIVAR...) returns ~4736 Da.
    """
    masses = [_AA_AVG_MASS[a] for a in sequence if a in _AA_AVG_MASS]
    if not masses:
        return 0.0
    return sum(masses) + _WATER_MASS


def composition(sequence: str) -> list[dict]:
    """Per-AA count and percent over the 20 standard residues.

    Returns one entry per AA in alphabetical order, including zeros.
    """
    counts = Counter(c for c in sequence if c in _AA_AVG_MASS)
    total = sum(counts.values()) or 1  # avoid div/0; zero counts still report 0.0%
    return [
        {
            "aa": aa,
            "label": _AA_THREE_LETTER[aa],
            "count": counts.get(aa, 0),
            "percent": round(100.0 * counts.get(aa, 0) / total, 2),
        }
        for aa in _AA_ALPHABET
    ]


def hydrophobicity_profile(sequence: str, window: int = 9) -> list[float]:
    """Kyte-Doolittle sliding-window average. Output length = len(seq) - window + 1.

    Unknown residues contribute 0. Returns empty list if sequence shorter than
    window.
    """
    if window < 1 or len(sequence) < window:
        return []
    vals = [_KD_HYDROPATHY.get(a, 0.0) for a in sequence]
    out: list[float] = []
    running = sum(vals[:window])
    out.append(round(running / window, 4))
    for i in range(window, len(vals)):
        running += vals[i] - vals[i - window]
        out.append(round(running / window, 4))
    return out


def _parse_ss_records_from_pdb(pdb_path: Path | str) -> dict[str, list[dict]]:
    """Read HELIX and SHEET records from a PDB file.

    BioPython's PDBParser does not populate ``structure.header['helix']`` or
    ``structure.header['sheet']`` (they are ``None``), so we scan the source
    PDB file directly.

    HELIX columns (PDB v3.3):
      cols 1-6   record name "HELIX "
      cols 22-25 initSeqNum (right-justified)
      cols 34-37 endSeqNum  (right-justified)
      cols 72-76 length     (right-justified)

    SHEET columns (PDB v3.3):
      cols 1-6   record name "SHEET "
      cols 23-26 initSeqNum (right-justified)
      cols 34-37 endSeqNum  (right-justified)
      (no explicit length column; compute as end - init + 1)

    Returns a dict with lists of {"length": int} entries to match the shape
    we expect from BioPython's header (if/when it populates it).
    """
    helix_records: list[dict] = []
    sheet_records: list[dict] = []
    p = Path(pdb_path)
    if not p.exists():
        return {"helix": helix_records, "sheet": sheet_records}
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        return {"helix": helix_records, "sheet": sheet_records}

    for raw in text.splitlines():
        if raw.startswith("HELIX "):
            length = 0
            # Column 72-76 (0-indexed 71:76) holds the explicit length.
            try:
                length = int(raw[71:76].strip() or 0)
            except ValueError:
                length = 0
            if length == 0:
                # Fallback: compute from initSeqNum (22-25) and endSeqNum (34-37).
                try:
                    init = int(raw[21:25].strip())
                    end = int(raw[33:37].strip())
                    length = end - init + 1
                except ValueError:
                    length = 0
            if length > 0:
                helix_records.append({"length": length})
        elif raw.startswith("SHEET "):
            # SHEET has no explicit length column — compute it from start/end.
            try:
                init = int(raw[22:26].strip())
                end = int(raw[33:37].strip())
                length = end - init + 1
            except ValueError:
                length = 0
            if length > 0:
                sheet_records.append({"length": length})

    return {"helix": helix_records, "sheet": sheet_records}


def _count_polymer_residues(structure) -> int:
    """Total standard-residue count across model 1 of the structure."""
    try:
        model = next(structure.get_models())
    except StopIteration:
        return 0
    total = 0
    for chain in model.get_chains():
        for residue in chain.get_residues():
            if residue.id[0] == " ":  # standard polymer residue
                total += 1
    return total


def secondary_structure_percentages(
    structure, pdb_path: Path | str | None = None
) -> dict[str, float]:
    """Helix / sheet / coil fractions, summing to 1.0.

    Reads HELIX/SHEET records to count residues annotated in helices and
    sheets, and treats the remainder as coil.

    BioPython does NOT populate ``structure.header['helix']`` or
    ``['sheet']`` for PDB files — they are ``None``. So this function:
      1. Tries ``structure.header['helix']`` / ``['sheet']`` first (in case a
         future BioPython version or alternate parser exposes them).
      2. Falls back to scanning the PDB file at ``pdb_path`` for HELIX/SHEET
         records.

    If neither source has any SS data, returns all-coil.
    """
    header = getattr(structure, "header", {}) or {}
    helix_records = header.get("helix") or []
    sheet_records = header.get("sheet") or []

    # If header lacks SS records but we have a file path, parse it directly.
    if (not helix_records and not sheet_records) and pdb_path is not None:
        parsed = _parse_ss_records_from_pdb(pdb_path)
        helix_records = parsed["helix"]
        sheet_records = parsed["sheet"]

    helix_residues = 0
    sheet_residues = 0
    for rec in helix_records:
        try:
            length = int(rec.get("length", 0))
        except (TypeError, ValueError, AttributeError):
            length = 0
        helix_residues += length
    for rec in sheet_records:
        try:
            length = int(rec.get("length", 0))
        except (TypeError, ValueError, AttributeError):
            length = 0
        sheet_residues += length

    total = _count_polymer_residues(structure)
    if total == 0:
        return {"helix": 0.0, "sheet": 0.0, "coil": 1.0}

    helix_frac = min(helix_residues / total, 1.0)
    sheet_frac = min(sheet_residues / total, 1.0)
    if helix_frac + sheet_frac > 1.0:
        scale = 1.0 / (helix_frac + sheet_frac)
        helix_frac *= scale
        sheet_frac *= scale
    coil_frac = max(0.0, 1.0 - helix_frac - sheet_frac)
    return {
        "helix": round(helix_frac, 4),
        "sheet": round(sheet_frac, 4),
        "coil": round(coil_frac, 4),
    }


def property_distribution(sequence: str) -> dict[str, int]:
    """Counts across hydrophobic / polar / charged+/- / aromatic / cysteine.

    Categories are NOT mutually exclusive (aromatic also counts as
    hydrophobic for F, W, Y).
    """
    return {
        "hydrophobic": sum(1 for c in sequence if c in _HYDROPHOBIC),
        "polar": sum(1 for c in sequence if c in _POLAR),
        "charged_positive": sum(1 for c in sequence if c in _CHARGED_POS),
        "charged_negative": sum(1 for c in sequence if c in _CHARGED_NEG),
        "aromatic": sum(1 for c in sequence if c in _AROMATIC),
        "cysteine": sum(1 for c in sequence if c in _CYSTEINE),
    }
