/**
 * Pure helpers behind the viewer's chain tree (P10).
 *
 * Nothing here imports React, Zustand or Mol*, so the arithmetic that decides
 * what the tree offers is unit-testable on its own. Residue positions are the
 * same 1-based per-chain ordinals the rest of the app uses — see the key
 * convention at the top of `lib/residue.ts`.
 */

import {
  RESIDUE_CLASS_ORDER,
  residueClass,
  residueKey,
  type ResidueClass,
} from "@/lib/residue";

/** An inclusive, 1-based ordinal range within one chain. */
export interface ChainSegment {
  /** First residue ordinal, 1-based. */
  start: number;
  /** Last residue ordinal, inclusive. */
  end: number;
}

/**
 * Splits a chain into navigable ordinal ranges.
 *
 * The segment *size* scales with the chain, the segment *count* does not: a
 * 46-residue chain gets two 25-residue chips, a 2,000-residue chain gets
 * 20 chips of 100. Nothing is ever dropped — the last segment is clipped to
 * the real residue count, so the union of the segments is always exactly
 * `1..residueCount`. That is the point: a fixed chip count that truncated the
 * tail would silently hide the end of every long chain.
 *
 * @param residueCount how many residues the chain has
 * @param maxSegments how many chips the rail is willing to lay out
 * @param baseSize the smallest segment worth offering
 */
export function chainSegments(
  residueCount: number,
  maxSegments = 24,
  baseSize = 25,
): ChainSegment[] {
  if (residueCount <= 0) return [];

  let size = Math.max(1, Math.floor(baseSize));
  const limit = Math.max(1, Math.floor(maxSegments));
  while (Math.ceil(residueCount / size) > limit) size *= 2;

  const segments: ChainSegment[] = [];
  for (let start = 1; start <= residueCount; start += size) {
    segments.push({ start, end: Math.min(start + size - 1, residueCount) });
  }
  return segments;
}

/** Every residue key in an inclusive ordinal range, in ascending order. */
export function segmentKeys(
  chainLabel: string,
  segment: ChainSegment,
): string[] {
  const keys: string[] = [];
  for (let p = segment.start; p <= segment.end; p += 1) {
    keys.push(residueKey(chainLabel, p));
  }
  return keys;
}

/** Every residue key in a chain of `residueCount` residues. */
export function chainKeys(chainLabel: string, residueCount: number): string[] {
  return segmentKeys(chainLabel, { start: 1, end: residueCount });
}

export interface ClassShare {
  cls: ResidueClass;
  count: number;
  /** Fraction of the chain, 0-1. Zero for an empty sequence. */
  fraction: number;
}

/**
 * Counts the chain's residues by the same five classes the sequence panel
 * colours by, in the same order, so the tree's composition bar and the
 * sequence legend agree cell for cell.
 */
export function classShares(sequence: string): ClassShare[] {
  const counts = new Map<ResidueClass, number>(
    RESIDUE_CLASS_ORDER.map((cls) => [cls, 0]),
  );
  for (const aa of sequence) {
    const cls = residueClass(aa);
    counts.set(cls, (counts.get(cls) ?? 0) + 1);
  }
  const total = sequence.length;
  return RESIDUE_CLASS_ORDER.map((cls) => {
    const count = counts.get(cls) ?? 0;
    return { cls, count, fraction: total === 0 ? 0 : count / total };
  });
}

/**
 * How many of a chain's residues are in the current selection.
 *
 * Counts by walking the chain's own ordinals rather than the selection, so a
 * key for some other chain — or a stale key left by a previous structure —
 * can never inflate the number.
 */
export function selectedInChain(
  chainLabel: string,
  residueCount: number,
  selected: ReadonlySet<string>,
): number {
  if (selected.size === 0) return 0;
  let n = 0;
  for (let p = 1; p <= residueCount; p += 1) {
    if (selected.has(residueKey(chainLabel, p))) n += 1;
  }
  return n;
}
