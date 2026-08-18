import { describe, it, expect } from "vitest";
import {
  indexResidueRecords,
  residueClickPayload,
  residueIndicesForKeys,
  resolveResidueIndex,
  EMPTY_RESIDUE_INDEX,
  type ResidueRecord,
} from "@/lib/residue-map";
import { residueKey } from "@/lib/residue";

/**
 * Hand-built fixture modelled on the cases 1CRN cannot exercise. 1CRN numbers
 * chain A 1..46 contiguously — the one arrangement where the panel's ordinal
 * and `auth_seq_id` coincide — so a fixture that looks like 1CRN cannot detect
 * the two conventions being swapped.
 *
 * This one is deliberately hostile, in input-file order:
 *
 * | source | residue | chain | auth_seq_id | expected key |
 * |--------|---------|-------|-------------|--------------|
 * | 0      | 10      | A     | 27          | A:1          |  chain starts at 27 (cf. 6VXX)
 * | 1      | 11      | A     | 28          | A:2          |
 * | 2      | 12      | A     | 29          | A:3          |
 * | 3      | 13      | A     | 34          | A:4          |  gap: 30-33 unmodelled
 * | 4      | 14      | A     | 34          | A:5          |  insertion code: auth repeats
 * | 5      | 20      | B     | 101         | B:1          |  second chain restarts at 1
 * | 6      | 21      | B     | 102         | B:2          |
 * | 7      | 22      | B     | 103         | B:3          |
 *
 * Model residue indices are non-contiguous and never equal `ordinal - 1`, so a
 * mapping that quietly used the residue index as the ordinal also fails.
 */
const RECORDS: ResidueRecord[] = [
  { source: 0, residue: 10, label: "A", authSeqId: 27 },
  { source: 1, residue: 11, label: "A", authSeqId: 28 },
  { source: 2, residue: 12, label: "A", authSeqId: 29 },
  { source: 3, residue: 13, label: "A", authSeqId: 34 },
  { source: 4, residue: 14, label: "A", authSeqId: 34 },
  { source: 5, residue: 20, label: "B", authSeqId: 101 },
  { source: 6, residue: 21, label: "B", authSeqId: 102 },
  { source: 7, residue: 22, label: "B", authSeqId: 103 },
];

/**
 * A second fixture whose model residue indices INVERT file order.
 *
 * Mol* re-sorts atoms while building its hierarchy — that is precisely why
 * `residueSourceIndex` exists — so the model residue index is NOT guaranteed to
 * ascend with source-file position. `RECORDS` above cannot detect a sort keyed
 * on the wrong field, because there `residue` happens to be monotonic in
 * `source`. Here it is not, in both chains:
 *
 * | source | residue | chain | correct key | key if sorted by residue |
 * |--------|---------|-------|-------------|--------------------------|
 * | 0      | 50      | A     | A:1         | A:2                      |
 * | 1      | 20      | A     | A:2         | A:1                      |
 * | 2      | 90      | A     | A:3         | A:3                      |
 * | 3      | 40      | B     | B:1         | B:2                      |
 * | 4      | 30      | B     | B:2         | B:1                      |
 */
const INVERTED_RECORDS: ResidueRecord[] = [
  { source: 0, residue: 50, label: "A", authSeqId: 10 },
  { source: 1, residue: 20, label: "A", authSeqId: 11 },
  { source: 2, residue: 90, label: "A", authSeqId: 12 },
  { source: 3, residue: 40, label: "B", authSeqId: 10 },
  { source: 4, residue: 30, label: "B", authSeqId: 11 },
];

const EXPECTED: ReadonlyArray<readonly [string, number]> = [
  ["A:1", 10],
  ["A:2", 11],
  ["A:3", 12],
  ["A:4", 13],
  ["A:5", 14],
  ["B:1", 20],
  ["B:2", 21],
  ["B:3", 22],
];

describe("indexResidueRecords — numbering convention", () => {
  const index = indexResidueRecords(RECORDS);

  it("numbers each chain from 1 regardless of where auth_seq_id starts", () => {
    // 6VXX chain A starts at author residue 27; panel position 1 is that residue.
    expect(index.keyToResidue.get("A:1")).toBe(10);
    // The second chain restarts at 1 rather than continuing chain A's count.
    expect(index.keyToResidue.get("B:1")).toBe(20);
  });

  it("does NOT key residues by auth_seq_id", () => {
    // This is the canary for the whole convention. If someone replaced the
    // ordinal with auth_seq_id, every one of these would flip.
    expect(index.keyToResidue.has("A:27")).toBe(false);
    expect(index.keyToResidue.has("A:28")).toBe(false);
    expect(index.keyToResidue.has("A:34")).toBe(false);
    expect(index.keyToResidue.has("B:101")).toBe(false);
    expect(index.residueToKey.get(10)).toBe("A:1");
    expect(index.residueToKey.get(20)).toBe("B:1");
  });

  it("never produces the key auth_seq_id numbering would have produced", () => {
    for (const record of RECORDS) {
      expect(index.residueToKey.get(record.residue)).not.toBe(
        residueKey(record.label, record.authSeqId),
      );
    }
  });

  it("keeps ordinals dense across a gap in author numbering", () => {
    // auth 30-33 are unmodelled, but positions 3 and 4 stay adjacent.
    expect(index.residueToKey.get(12)).toBe("A:3");
    expect(index.residueToKey.get(13)).toBe("A:4");
  });

  it("distinguishes two residues that share an auth_seq_id (insertion code)", () => {
    // Residues 13 and 14 are both auth 34; keying on auth_seq_id would collide.
    expect(index.residueToKey.get(13)).toBe("A:4");
    expect(index.residueToKey.get(14)).toBe("A:5");
    expect(index.keyToResidue.get("A:4")).not.toBe(index.keyToResidue.get("A:5"));
  });

  it("round-trips key -> residue -> key for every residue", () => {
    for (const [key, residue] of EXPECTED) {
      expect(index.keyToResidue.get(key)).toBe(residue);
      expect(index.residueToKey.get(residue)).toBe(key);
      expect(index.residueToKey.get(index.keyToResidue.get(key)!)).toBe(key);
    }
    expect(index.keyToResidue.size).toBe(EXPECTED.length);
    expect(index.residueToKey.size).toBe(EXPECTED.length);
  });

  it("counts residues per chain", () => {
    expect([...index.chainCounts]).toEqual([
      ["A", 5],
      ["B", 3],
    ]);
  });

  it("re-orders records that arrive out of file order", () => {
    const shuffled = [3, 7, 0, 5, 2, 6, 4, 1].map((i) => RECORDS[i]);
    const fromShuffled = indexResidueRecords(shuffled);
    for (const [key, residue] of EXPECTED) {
      expect(fromShuffled.keyToResidue.get(key)).toBe(residue);
    }
  });

  it("sorts by source-file position, not by model residue index", () => {
    // RECORDS alone cannot pin the sort KEY: its `residue` values happen to
    // ascend with `source`, so sorting by either produces the same answer.
    // INVERTED_RECORDS breaks that tie in both chains.
    const index2 = indexResidueRecords(INVERTED_RECORDS);

    // Correct (sort by source): A gets 50, 20, 90 in that order.
    // Sorting by residue would instead yield A:1 -> 20, A:2 -> 50.
    expect(index2.keyToResidue.get("A:1")).toBe(50);
    expect(index2.keyToResidue.get("A:2")).toBe(20);
    expect(index2.keyToResidue.get("A:3")).toBe(90);
    expect(index2.residueToKey.get(50)).toBe("A:1");
    expect(index2.residueToKey.get(20)).toBe("A:2");

    // Correct (sort by source): B gets 40 then 30.
    // Sorting by residue would instead yield B:1 -> 30, B:2 -> 40.
    expect(index2.keyToResidue.get("B:1")).toBe(40);
    expect(index2.keyToResidue.get("B:2")).toBe(30);
    expect(index2.residueToKey.get(40)).toBe("B:1");
    expect(index2.residueToKey.get(30)).toBe("B:2");

    // Stated as an invariant: the numerically smallest residue index in a
    // chain is not automatically that chain's first position.
    expect(index2.residueToKey.get(20)).not.toBe("A:1");
    expect(index2.residueToKey.get(30)).not.toBe("B:1");
  });

  it("handles interleaved chains by grouping on the chain label", () => {
    // A file that alternates A, B, A, B still numbers each chain 1, 2.
    const interleaved: ResidueRecord[] = [
      { source: 0, residue: 1, label: "A", authSeqId: 5 },
      { source: 1, residue: 2, label: "B", authSeqId: 5 },
      { source: 2, residue: 3, label: "A", authSeqId: 6 },
      { source: 3, residue: 4, label: "B", authSeqId: 6 },
    ];
    const index2 = indexResidueRecords(interleaved);
    expect(index2.keyToResidue.get("A:1")).toBe(1);
    expect(index2.keyToResidue.get("A:2")).toBe(3);
    expect(index2.keyToResidue.get("B:1")).toBe(2);
    expect(index2.keyToResidue.get("B:2")).toBe(4);
  });

  it("returns an empty index for no records", () => {
    const empty = indexResidueRecords([]);
    expect(empty.keyToResidue.size).toBe(0);
    expect(empty.residueToKey.size).toBe(0);
    expect(empty.chainCounts.size).toBe(0);
  });
});

describe("resolveResidueIndex", () => {
  const index = indexResidueRecords(RECORDS);

  it("reports empty space when there is no structural element", () => {
    expect(resolveResidueIndex(index, null)).toEqual({ kind: "empty" });
  });

  it("resolves an indexed polymer residue to its key", () => {
    expect(resolveResidueIndex(index, 13)).toEqual({
      kind: "residue",
      key: "A:4",
    });
  });

  it("reports unindexed geometry as 'unindexed', never as empty space", () => {
    // The 1HHO scenario: the user clicked the HEM cofactor, which the backend
    // parser skipped. Treating this as a background click would wipe the
    // selection even though the user hit real geometry.
    const hit = resolveResidueIndex(index, 999);
    expect(hit).toEqual({ kind: "unindexed", residue: 999 });
    expect(hit.kind).not.toBe("empty");
  });

  it("gives empty and unindexed distinct, non-overlapping shapes", () => {
    const empty = resolveResidueIndex(index, null);
    const unindexed = resolveResidueIndex(index, 999);
    expect(empty.kind).not.toBe(unindexed.kind);
  });

  it("treats every residue as unindexed against an empty index", () => {
    expect(resolveResidueIndex(EMPTY_RESIDUE_INDEX, 10)).toEqual({
      kind: "unindexed",
      residue: 10,
    });
  });
});

describe("residueClickPayload", () => {
  const index = indexResidueRecords(RECORDS);

  it("reports a residue key for an indexed residue", () => {
    expect(residueClickPayload(resolveResidueIndex(index, 13))).toBe("A:4");
  });

  it("reports null (clear the selection) only for genuine empty space", () => {
    expect(residueClickPayload(resolveResidueIndex(index, null))).toBeNull();
  });

  it("reports nothing at all for unindexed geometry", () => {
    // Clicking HEM in 1HHO must leave the current selection untouched, so the
    // payload has to be distinguishable from the `null` that means "clear".
    const payload = residueClickPayload(resolveResidueIndex(index, 999));
    expect(payload).toBeUndefined();
    expect(payload).not.toBeNull();
  });
});

describe("residueIndicesForKeys", () => {
  const index = indexResidueRecords(RECORDS);

  it("maps known keys to their model residue indices", () => {
    expect([...residueIndicesForKeys(index, ["A:1", "B:3"])].sort((a, b) => a - b)).toEqual([
      10, 22,
    ]);
  });

  it("ignores keys that are not in the index", () => {
    // Stale keys from a previously loaded protein must not throw.
    expect([...residueIndicesForKeys(index, ["A:1", "A:999", "Z:1", "A:27"])]).toEqual([10]);
  });

  it("returns an empty set for no keys", () => {
    expect(residueIndicesForKeys(index, []).size).toBe(0);
  });

  it("de-duplicates repeated keys", () => {
    expect(residueIndicesForKeys(index, ["A:1", "A:1"]).size).toBe(1);
  });
});
