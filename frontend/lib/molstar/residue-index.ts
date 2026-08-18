/**
 * Reconciles the sequence panel's 1-based ordinal numbering with Mol*'s
 * internal residue addressing.
 *
 * ## Why this exists
 *
 * The backend parser emits, per chain, a one-letter sequence built by walking
 * the chain's ATOM-record residues in file order. The sequence panel therefore
 * numbers residues `1..residue_count`. Mol* addresses residues by
 * `auth_seq_id`, which starts at whatever the file says and can contain gaps,
 * negative values, and insertion codes — so `auth_seq_id` and the panel's index
 * are NOT interchangeable.
 *
 * We resolve this once, at structure-load time, by building a bidirectional map
 * between the panel's ordinal key (`"A:12"`) and the **model residue index**
 * (Mol*'s exact internal residue handle). Using the residue index rather than
 * `auth_seq_id` also makes the mapping immune to insertion codes and to two
 * residues sharing a `auth_seq_id`.
 *
 * The residue filter here (`group_PDB === "ATOM"`, grouped by `auth_asym_id`,
 * in file order) mirrors `backend/app/services/parser.py`, which skips any
 * residue whose BioPython hetero-flag is set (waters, ligands, HETATM).
 */

import {
  Structure,
  StructureElement,
  Unit,
} from "molstar/lib/mol-model/structure";
import { SortedArray } from "molstar/lib/mol-data/int";
import { Loci } from "molstar/lib/mol-model/loci";
import { residueKey } from "@/lib/residue";

export interface ResidueIndexMap {
  /** `"A:12"` -> model residue index. */
  readonly keyToResidue: ReadonlyMap<string, number>;
  /** model residue index -> `"A:12"`. */
  readonly residueToKey: ReadonlyMap<number, string>;
  /** chain label -> number of polymer residues found for it. */
  readonly chainCounts: ReadonlyMap<string, number>;
}

export const EMPTY_RESIDUE_INDEX: ResidueIndexMap = {
  keyToResidue: new Map(),
  residueToKey: new Map(),
  chainCounts: new Map(),
};

/**
 * Assigns every ATOM-record residue of the pivot model the next 1-based ordinal
 * within its `auth_asym_id`, walking residues in **input-file order**.
 *
 * File order matters: Mol* may re-sort atoms while building its hierarchy, so
 * the hierarchy's own residue order is not guaranteed to match the order
 * BioPython saw. `residueSourceIndex` is the row of the residue's first atom in
 * the source file, which is exactly the order the backend counted in.
 */
export function buildResidueIndex(structure: Structure): ResidueIndexMap {
  const model = structure.models[0];
  if (!model) return EMPTY_RESIDUE_INDEX;

  const h = model.atomicHierarchy;
  const residueOfAtom = h.residueAtomSegments.index;
  const chainOffsets = h.chainAtomSegments.offsets;

  const entries: { label: string; residue: number; source: number }[] = [];

  for (let cI = 0, chainCount = h.chains._rowCount; cI < chainCount; cI++) {
    const atomStart = chainOffsets[cI];
    const atomEnd = chainOffsets[cI + 1];
    if (atomEnd <= atomStart) continue;

    const label = h.chains.auth_asym_id.value(cI);
    const first = residueOfAtom[atomStart];
    const last = residueOfAtom[atomEnd - 1];

    for (let rI = first; rI <= last; rI++) {
      // Mirrors the backend's `residue.id[0] != " "` skip (waters, ligands).
      if (h.residues.group_PDB.value(rI) !== "ATOM") continue;
      entries.push({
        label,
        residue: rI,
        source: h.residueSourceIndex.value(rI),
      });
    }
  }

  // Stable sort, so a model without source indices degrades to hierarchy order
  // rather than scrambling.
  entries.sort((a, b) => a.source - b.source);

  const keyToResidue = new Map<string, number>();
  const residueToKey = new Map<number, string>();
  const chainCounts = new Map<string, number>();

  for (const entry of entries) {
    const position = (chainCounts.get(entry.label) ?? 0) + 1;
    chainCounts.set(entry.label, position);
    const key = residueKey(entry.label, position);
    keyToResidue.set(key, entry.residue);
    residueToKey.set(entry.residue, key);
  }

  return { keyToResidue, residueToKey, chainCounts };
}

/**
 * Re-exported here so callers of the index get the drift check from the same
 * module. The implementation lives in `lib/residue.ts` because it needs no Mol*
 * types and is therefore cheap to unit-test.
 */
export { findIndexDrift } from "@/lib/residue";

/**
 * Resolves a clicked loci to a residue key. Bond loci are normalised to their
 * residue first so clicking a stick still lands on a residue. Returns `null`
 * for empty space or for anything outside the indexed polymer.
 */
export function lociToResidueKey(
  loci: Loci,
  index: ResidueIndexMap,
): string | null {
  const normalized = Loci.normalize(loci, "residue", true);
  if (!StructureElement.Loci.is(normalized)) return null;

  const location = StructureElement.Loci.getFirstLocation(normalized);
  if (!location || !Unit.isAtomic(location.unit)) return null;

  const residue = location.unit.residueIndex[location.element];
  return index.residueToKey.get(residue) ?? null;
}

/**
 * Builds a `StructureElement.Loci` covering every atom of every residue named
 * by `keys`. Unknown keys are ignored rather than throwing — the store may
 * still hold keys from a previously loaded protein.
 */
export function keysToLoci(
  structure: Structure,
  keys: readonly string[],
  index: ResidueIndexMap,
): StructureElement.Loci {
  const wanted = new Set<number>();
  for (const key of keys) {
    const residue = index.keyToResidue.get(key);
    if (residue !== undefined) wanted.add(residue);
  }
  if (wanted.size === 0) return StructureElement.Loci.none(structure);

  const model = structure.models[0];
  const elements: StructureElement.Loci["elements"][number][] = [];

  for (const unit of structure.units) {
    if (!Unit.isAtomic(unit) || unit.model !== model) continue;
    const unitElements = unit.elements;
    const indices: StructureElement.UnitIndex[] = [];
    for (let i = 0, il = unitElements.length; i < il; i++) {
      if (wanted.has(unit.residueIndex[unitElements[i]])) {
        indices.push(i as StructureElement.UnitIndex);
      }
    }
    if (indices.length > 0) {
      elements.push({ unit, indices: SortedArray.ofSortedArray(indices) });
    }
  }

  if (elements.length === 0) return StructureElement.Loci.none(structure);
  return StructureElement.Loci(structure, elements);
}
