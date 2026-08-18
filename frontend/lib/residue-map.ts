/**
 * The ordinal <-> residue-index mapping that underpins P4's selection sync,
 * with every Mol*-free step isolated here so it can be unit-tested against a
 * hand-built fixture (no WebGL, no `Structure`).
 *
 * `lib/molstar/residue-index.ts` is the thin adapter that reads a real Mol*
 * structure and feeds these functions.
 *
 * ## The convention this file enforces
 *
 * A residue key is `"<chainLabel>:<1-based ordinal within that chain>"`.
 * `authSeqId` is carried on each record for diagnostics only and is NEVER read
 * when assigning ordinals — see `indexResidueRecords`.
 */

import { residueKey } from "@/lib/residue";

/** One polymer residue as read out of a structure. */
export interface ResidueRecord {
  /** `auth_asym_id` — the chain label the sequence panel also uses. */
  readonly label: string;
  /** Mol*'s model residue index: the unique handle we map keys to. */
  readonly residue: number;
  /** Position of the residue's first atom in the source file. Drives ordering. */
  readonly source: number;
  /**
   * `auth_seq_id`, kept for diagnostics only. Deliberately unused by
   * `indexResidueRecords` — ordinals must not be derived from it.
   */
  readonly authSeqId: number;
}

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
 * Assigns each record the next 1-based ordinal within its chain, walking
 * records in **input-file order** (`source` ascending).
 *
 * File order matters: Mol* may re-sort atoms while building its hierarchy, so
 * hierarchy order is not guaranteed to match the order BioPython saw in
 * `backend/app/services/parser.py`. The sort is stable, so records without
 * meaningful source indices degrade to their given order rather than scrambling.
 *
 * `authSeqId` is never consulted. A chain starting at author residue 27 still
 * produces `A:1` for its first residue.
 */
export function indexResidueRecords(
  records: readonly ResidueRecord[],
): ResidueIndexMap {
  const ordered = [...records].sort((a, b) => a.source - b.source);

  const keyToResidue = new Map<string, number>();
  const residueToKey = new Map<number, string>();
  const chainCounts = new Map<string, number>();

  for (const record of ordered) {
    const position = (chainCounts.get(record.label) ?? 0) + 1;
    chainCounts.set(record.label, position);
    const key = residueKey(record.label, position);
    keyToResidue.set(key, record.residue);
    residueToKey.set(record.residue, key);
  }

  return { keyToResidue, residueToKey, chainCounts };
}

/**
 * What a click landed on.
 *
 * `empty` and `unindexed` are deliberately distinct: only `empty` (the user
 * clicked background) may clear the selection. `unindexed` means the user hit
 * real geometry that is not part of the indexed polymer — a ligand such as HEM,
 * a water, or a HETATM-coded residue the backend parser skipped — and the
 * current selection must survive it.
 */
export type LocusResolution =
  | { kind: "empty" }
  | { kind: "unindexed"; residue: number }
  | { kind: "residue"; key: string };

/**
 * Classifies a resolved model residue index. Pass `null` when the click
 * produced no structural element at all.
 */
export function resolveResidueIndex(
  index: ResidueIndexMap,
  residue: number | null,
): LocusResolution {
  if (residue === null) return { kind: "empty" };
  const key = index.residueToKey.get(residue);
  return key === undefined ? { kind: "unindexed", residue } : { kind: "residue", key };
}

/**
 * What, if anything, a click should report to `onResidueClick`.
 *
 * Returns `undefined` — meaning "say nothing" — for unindexed geometry. This is
 * the distinction that keeps a click on a ligand from being mistaken for a
 * background click and wiping the selection. `null` (clear) is reserved for a
 * genuine empty-space click.
 */
export function residueClickPayload(
  hit: LocusResolution,
): string | null | undefined {
  switch (hit.kind) {
    case "residue":
      return hit.key;
    case "empty":
      return null;
    case "unindexed":
      return undefined;
  }
}

/**
 * Maps residue keys to the model residue indices they name. Unknown keys are
 * ignored rather than throwing — the store may still hold keys from a
 * previously loaded protein.
 */
export function residueIndicesForKeys(
  index: ResidueIndexMap,
  keys: readonly string[],
): Set<number> {
  const wanted = new Set<number>();
  for (const key of keys) {
    const residue = index.keyToResidue.get(key);
    if (residue !== undefined) wanted.add(residue);
  }
  return wanted;
}
