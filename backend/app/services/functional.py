"""A5 — functional regions and binding pockets. Phase 1: annotation + rules.

Three sources of truth, kept apart on purpose:

1. **UniProt curation** — `ft_act_site`, `ft_binding`, `ft_site`, `ft_dna_bind`.
   A curator's claim about the *protein*, indexed against the *UniProt
   sequence*.
2. **This coordinate file** — the HETATM groups actually present and the
   polymer residues within heavy-atom contact distance of them. Measured, not
   inferred.
3. **Residue chemistry** — Kyte-Doolittle hydropathy, formal side-chain charge,
   and Shrake-Rupley solvent accessibility computed from the coordinates.

## What this module deliberately does NOT do

It does not predict pockets. A5's third bullet asks for "predicted pocket
regions" and Phase 2 is where an ML scorer would go; a geometric cavity search
shipped under that label in Phase 1 would be a heuristic wearing a prediction's
clothes. So the only thing called a pocket here is a set of residues observed
touching a ligand that is present in the file, and an apo structure is told
plainly that there is nothing to show rather than shown a guess.

## The hazard this module exists to survive

**A UniProt sequence position is not a structure residue number.** An AlphaFold
model covers the full UniProt sequence so the two coincide; a PDB entry almost
never does. Hen egg-white lysozyme is the canonical case: UniProt P00698 numbers
an 18-residue signal peptide that no crystal structure contains, so the curated
active sites at UniProt 53 and 70 are Glu35 and Asp52 in every lysozyme entry
ever deposited. Reading "53" as the 53rd residue, or as the residue labelled 53,
marks Ser50 or Ile55 instead — a confident, precise, plausible-looking lie.

So positions are mapped by **globally aligning the UniProt sequence against each
chain's parsed sequence** (`compare.build_aligner()` — the same alignment model
P7 pairs residues with) and reading the correspondence out of the alignment. The
result is expressed in the parser's residue **ordinals**, which is the
coordinate system `frontend/lib/molstar/residue-index.ts` already mirrors, so
nothing about the selection seam changes.

When the alignment does not support a chain — too short to be unambiguous, too
divergent to be the same molecule, too large to align inside a request — that
chain is **refused**, with the reason published in `ChainMapping`. When a
position has no counterpart in any chain, the site is returned with `located`
false and an explanation. An unplaced annotation shown as text is useful. A
misplaced one drawn in 3D is a lie.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Bio.PDB import NeighborSearch
from Bio.PDB.SASA import ShrakeRupley

from app.models.functional import (
    BoundLigand,
    ChainMapping,
    CuratedSite,
    FunctionalRegions,
    LigandContact,
    PriorityResidue,
    ResidueRef,
    SiteKind,
    SurfaceProfile,
)
from app.models.protein import ProteinSummary
from app.services.analytics import KD_HYDROPATHY
from app.services.compare import GAP, UNKNOWN_RESIDUE, build_aligner
from app.services.external import Metadata, as_int
from app.services.parser import to_one_letter

logger = logging.getLogger(__name__)

# --------------------------------------------------------------- thresholds

#: Heavy-atom distance that defines a ligand contact. 4.0 A is the conventional
#: cutoff for a binding-site residue (it covers hydrogen bonds at ~2.8-3.2 A and
#: van der Waals contact at ~3.4-4.0 A). Published in the response, because a
#: contact list means nothing without the distance that produced it.
CONTACT_CUTOFF_ANGSTROMS = 4.0

#: Relative solvent accessibility at or above which a residue counts as surface.
#: 0.25 is the standard exposed/buried split (Rost & Sander 1994).
EXPOSURE_THRESHOLD = 0.25

#: Fewer comparable columns than this and a best-scoring alignment position is
#: not distinguishable from coincidence in a 20-letter alphabet — an exact
#: 3-residue match turns up by chance in a protein of a few hundred residues.
#: This is an anti-coincidence floor, not a size limit: nothing is truncated by
#: it and it does not grow with the input.
MIN_ALIGNABLE_RESIDUES = 4

#: Percent identity, over comparable columns, below which a chain is not
#: accepted as this UniProt entry's product. A crystallised construct of the
#: right protein aligns at ~100%; a binding partner or an antibody chain in the
#: same file does not come close.
MIN_MAPPING_IDENTITY = 90.0

#: Identities as a percent of the SHORTER of (chain, UniProt sequence). Over the
#: shorter one, so a 99-residue mature protease still scores 100% against a
#: 1435-residue polyprotein, and a 130-residue target inside an MBP fusion still
#: scores against its own length rather than the tag's.
MIN_MAPPING_COVERAGE = 50.0

#: Global alignment is O(len_a * len_b), so the bound is on the actual work
#: rather than on either length. 16M cells is what `compare.py` already treats
#: as the interactive limit (4000 x 4000).
MAX_ALIGNMENT_CELLS = 4000 * 4000

#: Atom count past which Shrake-Rupley is skipped rather than run. Measured on
#: this project's own machine at ~0.1 ms per atom (1001 atoms / 0.12 s for
#: 1HEW; 9392 atoms / 0.94 s for the EGFR AlphaFold model), so 30k atoms is
#: about three seconds — the point at which a rail tab stops feeling like a
#: tab. Nothing is truncated by it: hydropathy and charge are returned in full
#: either way, and the response says the accessibility arrays are absent.
MAX_SASA_ATOMS = 30_000

#: ECO codes UniProt uses for experimentally-backed manual assertions. Anything
#: else (ECO:0000255 sequence-rule, ECO:0000250 similarity) is an inference, and
#: the two must not read the same in the UI.
EXPERIMENTAL_EVIDENCE_CODES = frozenset({"ECO:0000269", "ECO:0007744"})

#: Solvent names. Waters are not ligands, and they are not part of the surface
#: calculation either.
WATER_NAMES = frozenset({"HOH", "WAT", "DOD", "H2O", "TIP", "SOL"})

#: Backbone atoms that mark a hetero group as an amino acid sitting *inside* the
#: polymer (selenomethionine, phosphoserine, ...) rather than a bound ligand.
#: Deliberately conservative: it will also skip a free amino acid bound as a
#: substrate, which under-reports rather than mis-marks, and under-reporting is
#: the right direction to fail in here.
_PEPTIDE_BACKBONE = ("N", "CA", "C")

#: UniProt feature type -> the bucket it is reported in.
SITE_KIND_BY_FEATURE: dict[str, SiteKind] = {
    "Active site": "active_site",
    "Binding site": "binding_site",
    "Site": "site",
    "DNA binding": "dna_binding",
}

#: Theoretical maximum solvent-accessible area per residue, in A^2, from
#: Tien et al. (2013) PLoS ONE 8(11):e80635 — the Gly-X-Gly tripeptide values.
#: Used as the denominator for relative accessibility.
MAX_ACCESSIBLE_AREA: dict[str, float] = {
    "A": 129.0, "R": 274.0, "N": 195.0, "D": 193.0, "C": 167.0,
    "E": 223.0, "Q": 225.0, "G": 104.0, "H": 224.0, "I": 197.0,
    "L": 201.0, "K": 236.0, "M": 224.0, "F": 240.0, "P": 159.0,
    "S": 155.0, "T": 172.0, "W": 285.0, "Y": 263.0, "V": 174.0,
}

#: Formal side-chain charge at pH 7. Histidine is 0 on purpose: its side-chain
#: pKa is ~6.0, so calling it +1 at pH 7 overstates the claim. It is counted
#: separately instead.
FORMAL_CHARGE: dict[str, int] = {"D": -1, "E": -1, "K": 1, "R": 1}

NOT_PREDICTED_NOTE = (
    "Pockets shown here are observed: they are the residues in contact with a "
    "ligand present in this coordinate file. ProteoLens does not predict pockets "
    "in a structure that has no bound ligand."
)


# ------------------------------------------------------------ chain residues


@dataclass(frozen=True)
class ChainResidues:
    """One chain's parsed residues, with the file's own numbering alongside.

    `sequence[i]` is the residue at ordinal `i + 1`, which is the coordinate
    the selection key uses. `auth_seq_ids[i]` and `insertion_codes[i]` are the
    same residue's number and insertion code as written in the file — display
    only, and never an index into anything.
    """

    label: str
    sequence: str
    auth_seq_ids: tuple[int | None, ...]
    insertion_codes: tuple[str | None, ...]

    def ref(self, ordinal: int) -> ResidueRef:
        index = ordinal - 1
        return ResidueRef(
            chain=self.label,
            ordinal=ordinal,
            key=f"{self.label}:{ordinal}",
            residue=self.sequence[index],
            auth_seq_id=self.auth_seq_ids[index],
            insertion_code=self.insertion_codes[index],
        )


class ChainReadError(RuntimeError):
    """The structure's chains do not match the summary the parser produced."""


def read_chain_residues(structure, summary: ProteinSummary) -> list[ChainResidues]:
    """Re-walk the structure with the parser's filter, keeping file numbering.

    The parser returns one-letter sequences but no residue numbers, and the
    numbers are needed for display. Rather than trusting that a second walk
    lands on the same residues, every chain's re-derived sequence is compared
    against the one `parse()` produced and a mismatch raises: if the two ever
    disagree, every ordinal after the divergence is wrong, which is exactly the
    silent misplacement this module exists to prevent.
    """
    try:
        model = next(structure.get_models())
    except StopIteration:
        return []

    expected = {chain.label: chain.sequence for chain in summary.chains}
    out: list[ChainResidues] = []

    for chain in model.get_chains():
        letters: list[str] = []
        numbers: list[int | None] = []
        codes: list[str | None] = []
        for residue in chain.get_residues():
            # Mirrors `parser.parse`: hetero flag set means water, ligand, or a
            # modified residue, and none of those are in the ordinal numbering.
            if residue.id[0] != " ":
                continue
            one, _ = to_one_letter(residue.get_resname())
            letters.append(one)
            numbers.append(as_int(residue.id[1]))
            icode = residue.id[2]
            codes.append(icode.strip() or None if isinstance(icode, str) else None)

        sequence = "".join(letters)
        if not sequence:
            # The parser drops these chains too (ligand-only, nucleic-only), so
            # they carry no ordinals and cannot be selected.
            continue
        if expected.get(chain.id) != sequence:
            raise ChainReadError(
                f"Chain {chain.id} re-read as {len(sequence)} residues, but the parser "
                f"reported {len(expected.get(chain.id) or '')}. Refusing to number "
                "residues against a structure the parser saw differently."
            )
        out.append(
            ChainResidues(
                label=chain.id,
                sequence=sequence,
                auth_seq_ids=tuple(numbers),
                insertion_codes=tuple(codes),
            )
        )
    return out


# ------------------------------------------------------------- the mapping


@dataclass(frozen=True)
class PositionMap:
    """UniProt position -> every residue in this structure that carries it.

    A homo-oligomer maps one UniProt position onto one residue per copy, which
    is why the value is a list: marking only the first chain's copy of an active
    site would leave the other subunits' copies unmarked and unexplained.
    """

    positions: dict[int, list[ResidueRef]]
    chains: list[ChainMapping]

    @property
    def any_mapped(self) -> bool:
        return any(chain.mapped for chain in self.chains)


def map_uniprot_positions(
    uniprot_sequence: str, chains: list[ChainResidues]
) -> PositionMap:
    """Relate every UniProt sequence position to residue ordinals, or refuse.

    Pure: sequences in, mapping out, no I/O and no structure objects. That is
    what makes the off-by-one cases testable directly rather than only through
    an endpoint.
    """
    mapping: dict[int, list[ResidueRef]] = {}
    reports: list[ChainMapping] = []
    reference = (uniprot_sequence or "").strip().upper()

    for chain in chains:
        report, pairs = _map_one_chain(reference, chain)
        reports.append(report)
        if not report.mapped:
            continue
        for uniprot_position, ordinal in pairs:
            mapping.setdefault(uniprot_position, []).append(chain.ref(ordinal))

    return PositionMap(positions=mapping, chains=reports)


def _map_one_chain(
    reference: str, chain: ChainResidues
) -> tuple[ChainMapping, list[tuple[int, int]]]:
    """Align one chain to the UniProt sequence and decide whether to trust it."""
    blank = ChainMapping(
        chain=chain.label, mapped=False, residue_count=len(chain.sequence)
    )

    if len(reference) < MIN_ALIGNABLE_RESIDUES:
        return (
            blank.model_copy(
                update={"note": "UniProt returned no usable sequence for this entry."}
            ),
            [],
        )
    if len(chain.sequence) < MIN_ALIGNABLE_RESIDUES:
        return (
            blank.model_copy(
                update={
                    "note": f"Chain {chain.label} has {len(chain.sequence)} residue(s); "
                    f"fewer than {MIN_ALIGNABLE_RESIDUES} cannot be aligned to a "
                    "sequence position without guessing."
                }
            ),
            [],
        )
    if len(reference) * len(chain.sequence) > MAX_ALIGNMENT_CELLS:
        return (
            blank.model_copy(
                update={
                    "note": f"Aligning {len(chain.sequence)} residues against a "
                    f"{len(reference)}-residue entry is past this endpoint's "
                    "interactive limit, so no position is placed on this chain."
                }
            ),
            [],
        )

    alignment = build_aligner().align(reference, chain.sequence)[0]
    row_reference, row_chain = str(alignment[0]), str(alignment[1])

    pairs: list[tuple[int, int]] = []
    aligned_columns = 0
    comparable = 0
    identities = 0
    reference_index = 0
    chain_index = 0

    for left, right in zip(row_reference, row_chain):
        if left != GAP and right != GAP:
            aligned_columns += 1
            pairs.append((reference_index + 1, chain_index + 1))
            # 'X' is the parser's placeholder for a non-standard residue. It is
            # evidence of nothing, so it counts as neither a match nor a
            # mismatch — it leaves the denominator instead of deflating it.
            if right != UNKNOWN_RESIDUE:
                comparable += 1
                if left == right:
                    identities += 1
        if left != GAP:
            reference_index += 1
        if right != GAP:
            chain_index += 1

    identity_percent = round(100.0 * identities / comparable, 2) if comparable else 0.0
    denominator = min(len(chain.sequence), len(reference))
    coverage_percent = round(100.0 * identities / denominator, 2) if denominator else 0.0

    report = blank.model_copy(
        update={
            "aligned_columns": aligned_columns,
            "identity_percent": identity_percent,
            "coverage_percent": coverage_percent,
        }
    )

    if comparable < MIN_ALIGNABLE_RESIDUES:
        return (
            report.model_copy(
                update={
                    "note": f"Only {comparable} column(s) of chain {chain.label} could "
                    "be compared to the UniProt sequence — too few to place a position "
                    "on."
                }
            ),
            [],
        )
    if identity_percent < MIN_MAPPING_IDENTITY or coverage_percent < MIN_MAPPING_COVERAGE:
        return (
            report.model_copy(
                update={
                    "note": f"Chain {chain.label} aligns to this UniProt entry at "
                    f"{identity_percent}% identity over {coverage_percent}% of the "
                    "shorter sequence. That is not close enough to be the same "
                    "molecule, so no curated position is placed on this chain.",
                }
            ),
            [],
        )

    first_reference, first_ordinal = pairs[0]
    last_reference, last_ordinal = pairs[-1]
    first_auth = chain.auth_seq_ids[first_ordinal - 1]
    last_auth = chain.auth_seq_ids[last_ordinal - 1]
    return (
        report.model_copy(
            update={
                "mapped": True,
                "uniprot_start": first_reference,
                "uniprot_end": last_reference,
                "offset_note": (
                    f"UniProt {first_reference}-{last_reference} covers chain "
                    f"{chain.label} residues {first_ordinal}-{last_ordinal} "
                    f"(numbered {first_auth}-{last_auth} in the file)."
                ),
            }
        ),
        pairs,
    )


# --------------------------------------------------- curated site projection


def curated_sites(
    entry: Metadata, position_map: PositionMap, accession: str
) -> dict[SiteKind, list[CuratedSite]]:
    """Project UniProt's positional features onto this structure. Pure.

    Every feature is returned, placed or not. A curated site this crystallised
    construct simply does not contain is a fact about the structure worth
    stating, and stating it is the only alternative to inventing a position.
    """
    buckets: dict[SiteKind, list[CuratedSite]] = {
        "active_site": [],
        "binding_site": [],
        "site": [],
        "dna_binding": [],
    }
    reference = entry_sequence(entry)

    for feature in entry.get("features") or []:
        if not isinstance(feature, dict):
            continue
        kind = SITE_KIND_BY_FEATURE.get(_text(feature.get("type")) or "")
        if kind is None:
            continue
        site = _build_site(feature, kind, reference, position_map, accession)
        if site is not None:
            buckets[kind].append(site)

    for bucket in buckets.values():
        bucket.sort(key=lambda site: (site.uniprot_start, site.uniprot_end))
    return buckets


def _build_site(
    feature: dict[str, object],
    kind: SiteKind,
    reference: str,
    position_map: PositionMap,
    accession: str,
) -> CuratedSite | None:
    raw_location = feature.get("location")
    location = raw_location if isinstance(raw_location, dict) else {}
    start = as_int((location.get("start") or {}).get("value"))
    end = as_int((location.get("end") or {}).get("value"))
    if start is None or end is None or start < 1 or end < start:
        # UniProt writes an unknown boundary as a null value with an "UNKNOWN"
        # modifier. There is no position to place, and no honest guess.
        logger.info("Skipping a %s feature with no resolvable location", kind)
        return None

    description = _text(feature.get("description"))
    raw_ligand = feature.get("ligand")
    ligand = raw_ligand if isinstance(raw_ligand, dict) else {}
    raw_part = feature.get("ligandPart")
    part = raw_part if isinstance(raw_part, dict) else {}
    ligand_name = _text(ligand.get("name"))
    evidence_codes = _evidence_codes(feature)

    site = CuratedSite(
        kind=kind,
        label=_site_label(kind, description, ligand_name),
        description=description,
        ligand=ligand_name,
        ligand_id=_text(ligand.get("id")),
        ligand_part=_text(part.get("name")),
        evidence_codes=evidence_codes,
        experimental=any(code in EXPERIMENTAL_EVIDENCE_CODES for code in evidence_codes),
        uniprot_start=start,
        uniprot_end=end,
        uniprot_residues=reference[start - 1 : end],
    )

    # An isoform-scoped feature is indexed against a sequence we did not fetch
    # and did not align. Placing it on the canonical numbering would be off by
    # however much that isoform differs.
    isoform = _text(location.get("sequence"))
    if isoform is not None and isoform != accession:
        return site.model_copy(
            update={
                "location_note": f"This feature is annotated on isoform {isoform}, not "
                f"on {accession}, so it is not placed on this structure."
            }
        )

    if not position_map.any_mapped:
        return site.model_copy(
            update={
                "location_note": "No chain in this structure could be aligned to the "
                "UniProt sequence, so no curated position is placed."
            }
        )

    refs: list[ResidueRef] = []
    missing: list[int] = []
    for position in range(start, end + 1):
        found = position_map.positions.get(position)
        if found:
            refs.extend(found)
        else:
            missing.append(position)

    if not refs:
        return site.model_copy(update={"location_note": _missing_note(start, end)})

    substitutions = [
        f"{ref.key} is {ref.residue} here but {reference[position - 1]} in UniProt"
        for position in range(start, end + 1)
        for ref in position_map.positions.get(position, [])
        if 0 < position <= len(reference) and ref.residue != reference[position - 1]
    ]
    note = ""
    if missing:
        note = (
            f"{len(missing)} of {end - start + 1} position(s) in this feature are not "
            f"present in the structure: {_range_text(missing)}."
        )
    return site.model_copy(
        update={
            "positions": refs,
            "located": True,
            "location_note": note,
            "substitutions": substitutions,
        }
    )


def _missing_note(start: int, end: int) -> str:
    where = f"position {start}" if start == end else f"positions {start}-{end}"
    return (
        f"UniProt {where} could not be located in this structure — outside the "
        "modelled construct, or unmodelled within it."
    )


def _range_text(positions: list[int]) -> str:
    """Collapse a sorted position list into runs, so a 40-gap reads as one span."""
    runs: list[str] = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position == previous + 1:
            previous = position
            continue
        runs.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = position
    runs.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(runs)


def _site_label(kind: SiteKind, description: str | None, ligand: str | None) -> str:
    base = {
        "active_site": "Active site",
        "binding_site": "Binding site",
        "site": "Site",
        "dna_binding": "DNA-binding region",
    }[kind]
    if ligand:
        return f"{base} ({ligand})"
    if description:
        return f"{base}: {description}"
    return base


def _evidence_codes(feature: dict[str, object]) -> list[str]:
    codes: list[str] = []
    for evidence in feature.get("evidences") or []:
        if not isinstance(evidence, dict):
            continue
        code = _text(evidence.get("evidenceCode"))
        if code and code not in codes:
            codes.append(code)
    return codes


def entry_sequence(entry: Metadata) -> str:
    """The canonical sequence off a UniProtKB entry, uppercased, or ''."""
    sequence = entry.get("sequence")
    value = sequence.get("value") if isinstance(sequence, dict) else None
    return value.strip().upper() if isinstance(value, str) else ""


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


# ------------------------------------------------------------ bound ligands


def bound_ligands(
    structure, chains: list[ChainResidues], *, cutoff: float = CONTACT_CUTOFF_ANGSTROMS
) -> list[BoundLigand]:
    """Every non-polymer group in the file, with the residues it touches.

    Observation, not inference: the contact is a measured heavy-atom distance
    between two atoms that are both in this file.

    Two exclusions, both deliberate. Waters, by name. And hetero groups
    carrying a complete N/CA/C backbone — RCSB codes selenomethionine as
    HETATM, so without that rule every SeMet structure would report a ligand
    bound in the middle of its own helix. The rule also skips a free amino acid
    bound as a substrate, which under-reports rather than mis-marks, and
    under-reporting is the right direction to fail in here.

    Contacts are found geometrically, never by chain label: a ligand written
    under chain A's `auth_asym_id` routinely sits against chain B.
    """
    try:
        model = next(structure.get_models())
    except StopIteration:
        return []

    by_label = {chain.label: chain for chain in chains}
    owner: dict[int, tuple[str, int]] = {}
    polymer_atoms: list[object] = []
    for chain in model.get_chains():
        if chain.id not in by_label:
            continue
        ordinal = 0
        for residue in chain.get_residues():
            if residue.id[0] != " ":
                continue
            ordinal += 1
            for atom in residue.get_atoms():
                if _is_hydrogen(atom):
                    continue
                owner[id(atom)] = (chain.id, ordinal)
                polymer_atoms.append(atom)

    if not polymer_atoms:
        return []
    search = NeighborSearch(polymer_atoms)

    ligands = [
        _describe_ligand(residue, chain.id, search, owner, by_label, cutoff)
        for chain in model.get_chains()
        for residue in chain.get_residues()
        if residue.id[0] != " " and not _is_solvent(residue) and not _is_in_polymer(residue)
    ]

    # Most-contacted first: the group actually sitting in a pocket outranks a
    # surface-bound ion, without either being hidden.
    ligands.sort(key=lambda item: (-len(item.contacts), item.chain, item.auth_seq_id or 0))
    return ligands


def _describe_ligand(
    residue,
    chain_label: str,
    search: NeighborSearch,
    owner: dict[int, tuple[str, int]],
    by_label: dict[str, ChainResidues],
    cutoff: float,
) -> BoundLigand:
    atoms = [atom for atom in residue.get_atoms() if not _is_hydrogen(atom)]
    closest: dict[tuple[str, int], float] = {}
    counts: dict[tuple[str, int], int] = {}

    for atom in atoms:
        for neighbour in search.search(atom.coord, cutoff):
            found = owner.get(id(neighbour))
            if found is None:
                continue
            distance = float(((atom.coord - neighbour.coord) ** 2).sum() ** 0.5)
            if distance < closest.get(found, float("inf")):
                closest[found] = distance
            counts[found] = counts.get(found, 0) + 1

    contacts = [
        LigandContact(
            **by_label[label].ref(ordinal).model_dump(),
            min_distance=round(distance, 2),
            atom_contacts=counts[(label, ordinal)],
        )
        for (label, ordinal), distance in closest.items()
    ]
    contacts.sort(key=lambda c: (c.min_distance, c.chain, c.ordinal))

    seq_id = as_int(residue.id[1])
    icode = residue.id[2]
    icode_text = icode.strip() or None if isinstance(icode, str) else None
    name = residue.get_resname().strip()
    return BoundLigand(
        component=name,
        chain=chain_label,
        auth_seq_id=seq_id,
        insertion_code=icode_text,
        label=f"{name} {seq_id}{icode_text or ''} (chain {chain_label})",
        atom_count=len(atoms),
        single_atom=len(atoms) == 1,
        contacts=contacts,
    )


def _is_hydrogen(atom) -> bool:
    element = (getattr(atom, "element", "") or "").strip().upper()
    if element:
        return element in ("H", "D")
    return atom.get_name().strip().startswith(("H", "D"))


def _is_solvent(residue) -> bool:
    return residue.get_resname().strip().upper() in WATER_NAMES


def _is_in_polymer(residue) -> bool:
    """True for a hetero group that is an amino acid sitting inside a chain."""
    names = {atom.get_name().strip().upper() for atom in residue.get_atoms()}
    return all(backbone in names for backbone in _PEPTIDE_BACKBONE)


# ---------------------------------------------------- surface, charge, SASA


def strip_non_polymer(structure) -> int:
    """Detach every hetero residue from model 1. Returns how many were removed.

    Solvent-accessible area is a property of a surface, and which surface is a
    choice. This one is the protein's own: waters left in place would bury the
    residues they happen to sit on, and a bound ligand would bury exactly the
    pocket residues the rest of this module is about to report.

    Mutating rather than copying is deliberate — the structure is parsed per
    request and is not shared — but it means order matters, so this is called
    from `build_functional_regions` between the ligand pass and the surface
    pass rather than hidden inside either of them.
    """
    try:
        model = next(structure.get_models())
    except StopIteration:
        return 0
    removed = 0
    for chain in model.get_chains():
        for residue in [r for r in chain.get_residues() if r.id[0] != " "]:
            chain.detach_child(residue.id)
            removed += 1
    return removed


def surface_profiles(
    structure, chains: list[ChainResidues]
) -> tuple[list[SurfaceProfile], str]:
    """Per-residue hydropathy, formal charge and relative accessibility.

    Hydropathy and charge come from residue identity, so they are always
    available. Accessibility comes from the coordinates via Shrake-Rupley and
    can be absent — for a structure large enough that the calculation would
    stop the request being interactive, the arrays are returned empty and the
    note says why, rather than the whole profile being withheld.

    Expects a structure `strip_non_polymer` has already been run over.
    """
    areas, note = _residue_areas(structure, chains)
    profiles = [_profile_for(chain, areas.get(chain.label, [])) for chain in chains]
    return profiles, note


def _residue_areas(
    structure, chains: list[ChainResidues]
) -> tuple[dict[str, list[float]], str]:
    """Shrake-Rupley area per residue, keyed by chain, in ordinal order."""
    try:
        model = next(structure.get_models())
    except StopIteration:
        return {}, "This file contains no model, so no surface was computed."

    wanted = {chain.label for chain in chains}
    atom_count = sum(
        1
        for chain in model.get_chains()
        if chain.id in wanted
        for residue in chain.get_residues()
        for _ in residue.get_atoms()
    )
    if atom_count == 0:
        return {}, "No polymer atoms remained after solvent removal."
    if atom_count > MAX_SASA_ATOMS:
        return {}, (
            f"Solvent accessibility was not computed: {atom_count} atoms is past the "
            f"{MAX_SASA_ATOMS}-atom limit this endpoint answers within. Hydropathy and "
            "charge below are unaffected."
        )

    ShrakeRupley().compute(model, level="R")
    areas: dict[str, list[float]] = {}
    for chain in model.get_chains():
        if chain.id not in wanted:
            continue
        areas[chain.id] = [
            float(getattr(residue, "sasa", 0.0) or 0.0)
            for residue in chain.get_residues()
        ]
    return areas, (
        "Solvent accessibility is Shrake-Rupley area over the polymer alone (waters and "
        "ligands removed), divided by the residue's theoretical maximum (Tien et al. "
        f"2013). At or above {EXPOSURE_THRESHOLD:.2f} counts as surface-exposed."
    )


def _profile_for(chain: ChainResidues, areas: list[float]) -> SurfaceProfile:
    hydropathy = [KD_HYDROPATHY.get(residue, 0.0) for residue in chain.sequence]
    charge = [FORMAL_CHARGE.get(residue, 0) for residue in chain.sequence]

    relative: list[float] = []
    exposed: list[bool] = []
    # A length mismatch means the SASA pass walked different residues from the
    # ordinal pass, which would shift every value by the difference. Drop the
    # accessibility rather than publish a shifted one.
    if len(areas) == len(chain.sequence):
        for residue, area in zip(chain.sequence, areas):
            maximum = MAX_ACCESSIBLE_AREA.get(residue)
            if maximum is None:
                relative.append(0.0)
                exposed.append(False)
                continue
            fraction = round(area / maximum, 3)
            relative.append(fraction)
            exposed.append(fraction >= EXPOSURE_THRESHOLD)
    elif areas:
        logger.warning(
            "Chain %s: %d SASA values for %d residues; dropping accessibility",
            chain.label,
            len(areas),
            len(chain.sequence),
        )

    surface_hydropathy: float | None = None
    surface_charge: int | None = None
    if exposed:
        picked = [value for value, flag in zip(hydropathy, exposed) if flag]
        surface_hydropathy = round(sum(picked) / len(picked), 4) if picked else 0.0
        surface_charge = sum(value for value, flag in zip(charge, exposed) if flag)

    return SurfaceProfile(
        chain=chain.label,
        sequence=chain.sequence,
        hydropathy=hydropathy,
        charge=charge,
        relative_accessibility=relative,
        surface_exposed=exposed,
        net_charge=sum(charge),
        histidine_count=chain.sequence.count("H"),
        mean_hydropathy=(
            round(sum(hydropathy) / len(hydropathy), 4) if hydropathy else 0.0
        ),
        surface_mean_hydropathy=surface_hydropathy,
        surface_net_charge=surface_charge,
    )


# --------------------------------------------------------- priority residues


def priority_residues(
    active_sites: list[CuratedSite],
    binding_sites: list[CuratedSite],
    ligands: list[BoundLigand],
    profiles: list[SurfaceProfile],
) -> list[PriorityResidue]:
    """Residues with a functional claim against them, most evidence first.

    There is no score, because nothing here was fitted to anything. A residue
    is listed because a curator marked it, or because it touches a ligand in
    this file, or both — and "both" is the only thing the ordering rewards.

    `Site` and `DNA binding` features are deliberately not inputs. They are
    regions rather than pockets (a DNA-binding domain is 190 residues), and
    folding them in would bury the handful of residues this list exists to
    surface under a whole domain's worth of rows.
    """
    collected: dict[str, dict[str, object]] = {}

    def record(ref: ResidueRef, reason: str, provenance: str, flag: str) -> None:
        entry = collected.setdefault(
            ref.key,
            {
                "ref": ref,
                "reasons": [],
                "provenance": [],
                "curated_active_site": False,
                "curated_binding_site": False,
                "ligand_contact": False,
            },
        )
        reasons = entry["reasons"]
        assert isinstance(reasons, list)
        if reason not in reasons:
            reasons.append(reason)
        kinds = entry["provenance"]
        assert isinstance(kinds, list)
        if provenance not in kinds:
            kinds.append(provenance)
        entry[flag] = True

    for site in active_sites:
        for ref in site.positions:
            record(ref, f"Curated: {site.label}", "uniprot", "curated_active_site")
    for site in binding_sites:
        for ref in site.positions:
            record(ref, f"Curated: {site.label}", "uniprot", "curated_binding_site")
    for ligand in ligands:
        for contact in ligand.contacts:
            record(
                contact,
                f"Contacts {ligand.label} at {contact.min_distance:.2f} A",
                "structure",
                "ligand_contact",
            )

    chemistry = {
        profile.chain: profile for profile in profiles
    }
    out: list[PriorityResidue] = []
    for entry in collected.values():
        ref = entry["ref"]
        assert isinstance(ref, ResidueRef)
        profile = chemistry.get(ref.chain)
        index = ref.ordinal - 1
        out.append(
            PriorityResidue(
                **ref.model_dump(),
                reasons=list(entry["reasons"]),  # type: ignore[arg-type]
                provenance=list(entry["provenance"]),  # type: ignore[arg-type]
                evidence_kinds=len(entry["provenance"]),  # type: ignore[arg-type]
                curated_active_site=bool(entry["curated_active_site"]),
                curated_binding_site=bool(entry["curated_binding_site"]),
                ligand_contact=bool(entry["ligand_contact"]),
                hydropathy=_at(profile.hydropathy if profile else [], index),
                charge=_at(profile.charge if profile else [], index),
                relative_accessibility=_at(
                    profile.relative_accessibility if profile else [], index
                ),
            )
        )

    out.sort(
        key=lambda residue: (
            -residue.evidence_kinds,
            not residue.curated_active_site,
            not residue.curated_binding_site,
            residue.chain,
            residue.ordinal,
        )
    )
    return out


def _at(values: list, index: int):  # type: ignore[type-arg]
    return values[index] if 0 <= index < len(values) else None


# ---------------------------------------------------------------- assembly


def build_functional_regions(
    uid: str,
    summary: ProteinSummary,
    structure,
    *,
    accession: str | None,
    resolution_note: str,
    entry: Metadata | None,
    curation_note: str = "",
) -> FunctionalRegions:
    """Assemble the whole payload. The only function here that is not pure.

    `entry` is None whenever there is no curated half to project — no
    accession, no UniProt record, or UniProt unreachable. The structure-derived
    half is computed regardless, because it is measured here and does not
    depend on anyone else's database being up.
    """
    payload = FunctionalRegions(
        id=uid,
        accession=accession,
        accession_resolved=accession is not None,
        resolution_note=resolution_note,
        contact_cutoff=CONTACT_CUTOFF_ANGSTROMS,
        notes=[NOT_PREDICTED_NOTE],
    )
    if curation_note:
        payload.notes.append(curation_note)

    try:
        chains = read_chain_residues(structure, summary)
    except ChainReadError as exc:
        # The two walks of the same file disagreed. Every ordinal after the
        # divergence would be wrong, so nothing positional is published.
        logger.warning("Refusing to number residues for %s: %s", uid, exc)
        payload.notes.append(
            "Residue numbering could not be verified against the parsed structure, so "
            "no residue is marked. This is a bug, not a property of your file."
        )
        return payload

    if not chains:
        payload.notes.append("This file contains no standard amino-acid chain.")
        return payload

    reference = entry_sequence(entry) if entry else ""
    position_map = map_uniprot_positions(reference, chains) if reference else None
    if position_map is not None:
        payload.chain_mappings = position_map.chains
        buckets = curated_sites(entry or {}, position_map, accession or "")
        payload.active_sites = buckets["active_site"]
        payload.binding_sites = buckets["binding_site"]
        payload.other_sites = buckets["site"]
        payload.dna_binding = buckets["dna_binding"]
        payload.unlocated_sites = sum(
            1
            for bucket in buckets.values()
            for site in bucket
            if not site.located
        )
        if payload.unlocated_sites:
            payload.notes.append(
                f"{payload.unlocated_sites} curated site(s) exist for this protein but "
                "could not be placed in this structure. They are listed without a "
                "position rather than guessed at."
            )

    payload.ligands = bound_ligands(structure, chains)
    if not payload.ligands:
        payload.notes.append(
            "No non-water ligand is present in this file, so no binding pocket is "
            "observed here."
        )

    # Order matters: the ligands have been measured, so the solvent and the
    # ligands can now come out before the surface is computed.
    strip_non_polymer(structure)
    payload.surface, payload.surface_note = surface_profiles(structure, chains)
    payload.priority_residues = priority_residues(
        payload.active_sites, payload.binding_sites, payload.ligands, payload.surface
    )
    return payload


def empty_functional_regions(
    uid: str, note: str, accession: str | None = None
) -> FunctionalRegions:
    """A valid, entirely empty payload — for a protein whose file is gone."""
    return FunctionalRegions(
        id=uid,
        accession=accession,
        accession_resolved=accession is not None,
        resolution_note=note,
        contact_cutoff=CONTACT_CUTOFF_ANGSTROMS,
        notes=[NOT_PREDICTED_NOTE],
    )
