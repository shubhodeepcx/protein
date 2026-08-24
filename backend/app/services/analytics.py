from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict

logger = logging.getLogger(__name__)

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

# Kyte-Doolittle hydropathy scale.
#
# Public (no leading underscore) because A5's per-residue surface profile reads
# the same scale this module's sliding-window profile averages. A second copy
# would be a second place for the numbers to drift.
KD_HYDROPATHY = {
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
    vals = [KD_HYDROPATHY.get(a, 0.0) for a in sequence]
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


_MMCIF_EXTS = frozenset({".cif", ".mmcif"})

# mmCIF spells "no value" as `?` and "not applicable" as `.`; MMCIF2Dict hands
# both through verbatim, so neither may be read as a chain id or a residue number.
_MMCIF_NULL_TOKENS = frozenset({"?", "."})

# `_struct_conf.conf_type_id` values. Every helix flavour is spelled with a
# `HELX` prefix (HELX_P, HELX_RH_AL_P, HELX_LH_PP_P, ...) and every extended
# strand with `STRN`. TURN_P / BEND / OTHER are neither, and correctly fall
# through to coil.
_MMCIF_HELIX_TYPE_PREFIX = "HELX"
_MMCIF_STRAND_TYPE_PREFIX = "STRN"

# Presence of ANY key under these categories means the file has a
# secondary-structure section, even if it turns out to hold only turns and
# bends. The trailing dot matters: it keeps `_struct_conf_type.*` — a different
# category, present in files that carry no `_struct_conf` rows — from counting.
_MMCIF_SS_CATEGORY_PREFIXES = ("_struct_conf.", "_struct_sheet_range.")


@dataclass(frozen=True)
class _ResidueRange:
    """One inclusive residue span on one chain, in one numbering scheme."""

    chain_id: str
    start: int
    end: int


@dataclass(frozen=True)
class _MMCIFSecondaryStructure:
    """Helix/strand spans read off an mmCIF, in both numbering schemes.

    mmCIF carries two parallel numberings: `label_*` (the canonical entity
    numbering) and `auth_*` (the depositor's, which is what the PDB records
    used). BioPython's ``MMCIFParser`` builds chains and residue ids from the
    `auth_*` columns by default, so those are tried first — but a hand-written
    or minimal mmCIF may only carry `label_*`, hence both are kept.
    """

    helix_auth: list[_ResidueRange]
    sheet_auth: list[_ResidueRange]
    helix_label: list[_ResidueRange]
    sheet_label: list[_ResidueRange]
    declared: bool


def _is_mmcif_path(path: Path | str) -> bool:
    return Path(path).suffix.lower() in _MMCIF_EXTS


def _cif_column(mmcif: dict[str, object], key: str) -> list[str]:
    """One mmCIF column as a list of raw string cells, row order preserved.

    ``MMCIF2Dict`` returns a list per key — one element per row of a looped
    category, and still a one-element list for a single-row category. A bare
    string is tolerated so a hand-written fixture cannot silently read as empty.
    Non-string cells become `""` rather than being dropped, because dropping
    would shift every later row against the other columns.
    """
    raw = mmcif.get(key)
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    try:
        cells = list(raw)  # type: ignore[call-overload]
    except TypeError:
        return []
    return [cell if isinstance(cell, str) else "" for cell in cells]


def _cif_int(value: str) -> int | None:
    """A residue number from an mmCIF cell, or None when it is null/malformed."""
    token = value.strip()
    if not token or token in _MMCIF_NULL_TOKENS:
        return None
    try:
        return int(token)
    except ValueError:
        return None


def _mmcif_ranges(
    mmcif: dict[str, object],
    category: str,
    scheme: str,
    keep: list[bool] | None = None,
) -> list[_ResidueRange]:
    """Residue spans from one mmCIF category in one numbering scheme.

    `keep` masks rows by index (used to split `_struct_conf` into helices and
    strands). Rows with a null chain id or an unparseable residue number are
    skipped rather than guessed at.
    """
    chains = _cif_column(mmcif, f"{category}.beg_{scheme}_asym_id")
    starts = _cif_column(mmcif, f"{category}.beg_{scheme}_seq_id")
    ends = _cif_column(mmcif, f"{category}.end_{scheme}_seq_id")
    rows = min(len(chains), len(starts), len(ends))

    ranges: list[_ResidueRange] = []
    for i in range(rows):
        if keep is not None and not (i < len(keep) and keep[i]):
            continue
        chain_id = chains[i].strip()
        if not chain_id or chain_id in _MMCIF_NULL_TOKENS:
            continue
        start = _cif_int(starts[i])
        end = _cif_int(ends[i])
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        ranges.append(_ResidueRange(chain_id=chain_id, start=start, end=end))
    return ranges


def _parse_ss_ranges_from_mmcif(cif_path: Path | str) -> _MMCIFSecondaryStructure:
    """Read helix and strand spans from an mmCIF's SS categories.

    mmCIF has no HELIX/SHEET text records — the same information lives in
    `_struct_conf` (helices, plus turns and bends, discriminated by
    `conf_type_id`) and `_struct_sheet_range` (strands). Every structure RCSB
    serves as `.cif` annotates SS this way, so scanning for `HELIX `/`SHEET `
    lines finds nothing and reports the entry as 100% coil.
    """
    empty = _MMCIFSecondaryStructure([], [], [], [], declared=False)
    p = Path(cif_path)
    if not p.exists():
        return empty
    try:
        mmcif: dict[str, object] = MMCIF2Dict(str(p))
    except (OSError, ValueError, KeyError, IndexError) as exc:
        logger.warning("Could not read mmCIF secondary structure from %s: %s", p.name, exc)
        return empty

    declared = any(
        key.startswith(prefix)
        for key in mmcif
        for prefix in _MMCIF_SS_CATEGORY_PREFIXES
    )

    conf_types = [t.strip().upper() for t in _cif_column(mmcif, "_struct_conf.conf_type_id")]
    helix_rows = [t.startswith(_MMCIF_HELIX_TYPE_PREFIX) for t in conf_types]
    # Some depositors put strands in `_struct_conf` as STRN as well as (or
    # instead of) in `_struct_sheet_range`; both are collected and the residue
    # counting below de-duplicates any overlap.
    strand_rows = [t.startswith(_MMCIF_STRAND_TYPE_PREFIX) for t in conf_types]

    return _MMCIFSecondaryStructure(
        helix_auth=_mmcif_ranges(mmcif, "_struct_conf", "auth", helix_rows),
        sheet_auth=(
            _mmcif_ranges(mmcif, "_struct_conf", "auth", strand_rows)
            + _mmcif_ranges(mmcif, "_struct_sheet_range", "auth")
        ),
        helix_label=_mmcif_ranges(mmcif, "_struct_conf", "label", helix_rows),
        sheet_label=(
            _mmcif_ranges(mmcif, "_struct_conf", "label", strand_rows)
            + _mmcif_ranges(mmcif, "_struct_sheet_range", "label")
        ),
        declared=declared,
    )


def _chain_ids(structure) -> set[str]:
    """Chain labels present in model 1 of the structure."""
    try:
        model = next(structure.get_models())
    except StopIteration:
        return set()
    return {chain.id for chain in model.get_chains()}


def _select_numbering(
    parsed: _MMCIFSecondaryStructure, chain_ids: set[str]
) -> tuple[list[_ResidueRange], list[_ResidueRange]]:
    """Pick the numbering scheme whose chain ids actually exist in the structure.

    `auth_*` is what BioPython builds chains from by default, so it wins when it
    matches. Falling back to `label_*` keeps minimal mmCIFs that only carry the
    canonical numbering working instead of silently counting zero residues.
    """
    auth = (parsed.helix_auth, parsed.sheet_auth)
    label = (parsed.helix_label, parsed.sheet_label)
    for helix, sheet in (auth, label):
        if any(r.chain_id in chain_ids for r in (*helix, *sheet)):
            return helix, sheet
    return auth


def _count_residues_in_ranges(structure, ranges: list[_ResidueRange]) -> int:
    """Standard residues of model 1 that fall inside any of `ranges`.

    Counting real residues (rather than trusting a declared span length) keeps
    the total honest when a range covers residues missing from the coordinates,
    and de-duplicates overlapping spans.
    """
    if not ranges:
        return 0
    try:
        model = next(structure.get_models())
    except StopIteration:
        return 0

    by_chain: dict[str, list[_ResidueRange]] = {}
    for r in ranges:
        by_chain.setdefault(r.chain_id, []).append(r)

    total = 0
    for chain in model.get_chains():
        spans = by_chain.get(chain.id)
        if not spans:
            continue
        for residue in chain.get_residues():
            if residue.id[0] != " ":  # skip waters, ligands, other heteroatoms
                continue
            seq_id = residue.id[1]
            if not isinstance(seq_id, int):
                continue
            if any(span.start <= seq_id <= span.end for span in spans):
                total += 1
    return total


def _sum_record_lengths(records: list[dict]) -> int:
    """Total residues declared by a list of {"length": int} SS records."""
    total = 0
    for rec in records:
        try:
            total += int(rec.get("length", 0))
        except (TypeError, ValueError, AttributeError):
            continue
    return total


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


@dataclass(frozen=True)
class SecondaryStructureResult:
    """Helix / sheet / coil fractions, plus whether the file declared any SS.

    ``available`` is False when the structure file carries no secondary-structure
    annotation at all — an AlphaFold prediction, for instance, has neither
    HELIX/SHEET records nor `_struct_conf`, because a predicted model has no
    assigned secondary structure. The fractions are then an all-coil
    *placeholder*, not a measurement, and callers should say so rather than draw
    a fully-coil chart as if it were a finding.
    """

    helix: float
    sheet: float
    coil: float
    available: bool


def _ss_fractions(
    helix_residues: int, sheet_residues: int, total: int
) -> tuple[float, float, float]:
    """Normalise annotated residue counts into fractions summing to 1.0."""
    if total == 0:
        return 0.0, 0.0, 1.0
    helix_frac = min(helix_residues / total, 1.0)
    sheet_frac = min(sheet_residues / total, 1.0)
    if helix_frac + sheet_frac > 1.0:
        scale = 1.0 / (helix_frac + sheet_frac)
        helix_frac *= scale
        sheet_frac *= scale
    coil_frac = max(0.0, 1.0 - helix_frac - sheet_frac)
    return round(helix_frac, 4), round(sheet_frac, 4), round(coil_frac, 4)


def secondary_structure(
    structure, path: Path | str | None = None
) -> SecondaryStructureResult:
    """Helix / sheet / coil fractions for a parsed structure, plus availability.

    Where the annotation comes from, in order:

      1. ``structure.header['helix'] / ['sheet']`` — BioPython does NOT populate
         these today (they are ``None``), but an alternate or future parser
         might, so they win when present.
      2. mmCIF (`.cif` / `.mmcif`): the `_struct_conf` and `_struct_sheet_range`
         categories, mapped onto the chains and residue numbers of `structure`.
      3. PDB: the `HELIX ` / `SHEET ` text records, which exist only in the
         legacy format.

    Nothing is *computed* here — DSSP-style assignment from coordinates is
    deliberately out of scope (it needs a native binary). This reads the
    secondary structure the file already declares.

    ``available`` reports whether the file declared anything at all. For mmCIF
    that is the presence of the SS categories, so a file whose `_struct_conf`
    holds only turns and bends still counts as annotated (it genuinely has no
    helices or strands). For PDB it is the presence of usable HELIX/SHEET
    records, since the format has no way to say "assigned, and there are none".
    """
    header = getattr(structure, "header", {}) or {}
    helix_records = header.get("helix") or []
    sheet_records = header.get("sheet") or []

    if helix_records or sheet_records:
        helix_residues = _sum_record_lengths(helix_records)
        sheet_residues = _sum_record_lengths(sheet_records)
        declared = True
    elif path is None:
        helix_residues = sheet_residues = 0
        declared = False
    elif _is_mmcif_path(path):
        parsed = _parse_ss_ranges_from_mmcif(path)
        helix_ranges, sheet_ranges = _select_numbering(parsed, _chain_ids(structure))
        helix_residues = _count_residues_in_ranges(structure, helix_ranges)
        sheet_residues = _count_residues_in_ranges(structure, sheet_ranges)
        declared = parsed.declared
    else:
        from_records = _parse_ss_records_from_pdb(path)
        helix_residues = _sum_record_lengths(from_records["helix"])
        sheet_residues = _sum_record_lengths(from_records["sheet"])
        declared = bool(from_records["helix"] or from_records["sheet"])

    helix_frac, sheet_frac, coil_frac = _ss_fractions(
        helix_residues, sheet_residues, _count_polymer_residues(structure)
    )
    if not declared:
        logger.info(
            "No secondary-structure annotation in %s; reporting all-coil as unavailable",
            Path(path).name if path is not None else "<no file>",
        )
    return SecondaryStructureResult(
        helix=helix_frac, sheet=sheet_frac, coil=coil_frac, available=declared
    )


def secondary_structure_percentages(
    structure, pdb_path: Path | str | None = None
) -> dict[str, float]:
    """Helix / sheet / coil fractions only, summing to 1.0.

    Thin view over :func:`secondary_structure` for callers that only want the
    three numbers. Prefer :func:`secondary_structure` — it also reports whether
    the file declared any secondary structure in the first place.
    """
    result = secondary_structure(structure, path=pdb_path)
    return {"helix": result.helix, "sheet": result.sheet, "coil": result.coil}


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
