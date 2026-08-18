/**
 * Mol*-facing adapter for the ordinal <-> residue-index mapping.
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
 * residues sharing an `auth_seq_id`.
 *
 * The residue filter here (`group_PDB === "ATOM"`, grouped by `auth_asym_id`,
 * in file order) mirrors `backend/app/services/parser.py`, which skips any
 * residue whose BioPython hetero-flag is set (waters, ligands, HETATM).
 *
 * All the numbering logic itself lives in `lib/residue-map.ts`, which is free
 * of Mol* imports and unit-tested there.
 */

import {
  Structure,
  StructureElement,
  Unit,
} from "molstar/lib/mol-model/structure";
import { SortedArray } from "molstar/lib/mol-data/int";
import { Loci } from "molstar/lib/mol-model/loci";
import {
  indexResidueRecords,
  residueIndicesForKeys,
  resolveResidueIndex,
  residueClickPayload,
  EMPTY_RESIDUE_INDEX,
  type LocusResolution,
  type ResidueIndexMap,
  type ResidueRecord,
} from "@/lib/residue-map";

export {
  residueClickPayload,
  EMPTY_RESIDUE_INDEX,
  type LocusResolution,
  type ResidueIndexMap,
  type ResidueRecord,
};

/**
 * Re-exported here so callers of the index get the drift check from the same
 * module. The implementation lives in `lib/residue.ts` because it needs no Mol*
 * types and is therefore cheap to unit-test.
 */
import { findIndexDrift, type QueryChain } from "@/lib/residue";

export { findIndexDrift };

/**
 * Logs a warning when Mol*'s per-chain residue counts disagree with the API's,
 * i.e. when the ordinal numbering the sequence panel renders would not line up
 * with what this index resolves. A warning rather than a throw, so an odd file
 * still renders — but the drift is never silent.
 */
export function warnOnResidueDrift(
  index: ResidueIndexMap,
  chains: readonly QueryChain[] | undefined,
): void {
  if (!chains) return;
  const drift = findIndexDrift(index, chains);
  if (drift.length === 0) return;
  // eslint-disable-next-line no-console
  console.warn(
    "Residue numbering drift between Mol* and the API:",
    drift.join("; "),
  );
}

/**
 * Reads every ATOM-record residue of the pivot model out of the atomic
 * hierarchy, tagged with its chain label, source-file position, and
 * `auth_seq_id`. Ordering and numbering are left to `indexResidueRecords`.
 */
export function extractResidueRecords(structure: Structure): ResidueRecord[] {
  const model = structure.models[0];
  if (!model) return [];

  const h = model.atomicHierarchy;
  const residueOfAtom = h.residueAtomSegments.index;
  const chainOffsets = h.chainAtomSegments.offsets;
  const records: ResidueRecord[] = [];

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
      records.push({
        label,
        residue: rI,
        source: h.residueSourceIndex.value(rI),
        authSeqId: h.residues.auth_seq_id.value(rI),
      });
    }
  }

  return records;
}

/** Builds the ordinal <-> residue-index map for a loaded structure. */
export function buildResidueIndex(structure: Structure): ResidueIndexMap {
  return indexResidueRecords(extractResidueRecords(structure));
}

/**
 * Resolves a clicked loci. Bond loci are normalised to their residue first so
 * clicking a stick still lands on a residue.
 *
 * Returns `{ kind: "empty" }` only when the click produced no structural
 * element — i.e. the user clicked background. Real geometry outside the indexed
 * polymer (a ligand, a water) returns `{ kind: "unindexed" }` so callers can
 * leave the current selection alone.
 */
export function resolveResidueLocus(
  loci: Loci,
  index: ResidueIndexMap,
): LocusResolution {
  const normalized = Loci.normalize(loci, "residue", true);
  if (!StructureElement.Loci.is(normalized)) {
    return resolveResidueIndex(index, null);
  }

  const location = StructureElement.Loci.getFirstLocation(normalized);
  if (!location || !Unit.isAtomic(location.unit)) {
    return resolveResidueIndex(index, null);
  }

  return resolveResidueIndex(index, location.unit.residueIndex[location.element]);
}

/**
 * Builds a `StructureElement.Loci` covering every atom of every residue named
 * by `keys`.
 */
export function keysToLoci(
  structure: Structure,
  keys: readonly string[],
  index: ResidueIndexMap,
): StructureElement.Loci {
  const wanted = residueIndicesForKeys(index, keys);
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
