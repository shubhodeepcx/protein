import { describe, it, expect } from "vitest";

import {
  chainKeys,
  chainSegments,
  classShares,
  segmentKeys,
  selectedInChain,
} from "@/lib/chain-stats";

describe("chainSegments", () => {
  it("covers every residue exactly once, with no gap and no overlap", () => {
    for (const count of [1, 25, 26, 46, 130, 999, 2000, 5001]) {
      const segs = chainSegments(count);
      expect(segs[0].start).toBe(1);
      expect(segs[segs.length - 1].end).toBe(count);
      for (let i = 1; i < segs.length; i += 1) {
        expect(segs[i].start).toBe(segs[i - 1].end + 1);
      }
    }
  });

  it("never truncates the tail of a long chain — it grows the segment instead", () => {
    // The failure mode this guards: a fixed chip count that silently stops
    // partway, hiding the end of every long chain.
    const segs = chainSegments(5000);
    expect(segs[segs.length - 1].end).toBe(5000);
    expect(segs.length).toBeLessThanOrEqual(24);
    // 5000 / 25 = 200 chips at the base size, so the size must have grown.
    expect(segs[0].end - segs[0].start + 1).toBeGreaterThan(25);
  });

  it("keeps the base segment size while the chain is short enough", () => {
    expect(chainSegments(46)).toEqual([
      { start: 1, end: 25 },
      { start: 26, end: 46 },
    ]);
  });

  it("returns nothing for a chain with no residues", () => {
    expect(chainSegments(0)).toEqual([]);
    expect(chainSegments(-3)).toEqual([]);
  });

  it("keeps the base size when the chain fills the budget exactly", () => {
    // 100 residues at the 25 base size is exactly 4 segments for a budget of
    // 4. Growing here — an off-by-one in the loop's comparison — would halve
    // the resolution of every chain that lands on the boundary.
    expect(chainSegments(100, 4, 25)).toEqual([
      { start: 1, end: 25 },
      { start: 26, end: 50 },
      { start: 51, end: 75 },
      { start: 76, end: 100 },
    ]);
  });

  it("respects a caller-supplied chip budget", () => {
    expect(chainSegments(1000, 4).length).toBeLessThanOrEqual(4);
    expect(chainSegments(1000, 4)[chainSegments(1000, 4).length - 1].end).toBe(
      1000,
    );
  });
});

describe("segmentKeys / chainKeys", () => {
  it("emits the canonical `<chain>:<ordinal>` keys, ascending and inclusive", () => {
    expect(segmentKeys("A", { start: 3, end: 6 })).toEqual([
      "A:3",
      "A:4",
      "A:5",
      "A:6",
    ]);
  });

  it("starts a whole chain at ordinal 1, not 0", () => {
    expect(chainKeys("B", 3)).toEqual(["B:1", "B:2", "B:3"]);
  });

  it("emits exactly one key per residue", () => {
    expect(chainKeys("A", 130)).toHaveLength(130);
  });
});

describe("classShares", () => {
  it("counts residues into the five sequence-panel classes", () => {
    // A,V hydrophobic · S,T polar · K positive · D negative · X other
    const shares = classShares("AVSTKDX");
    const byClass = Object.fromEntries(shares.map((s) => [s.cls, s.count]));
    expect(byClass).toEqual({
      hydrophobic: 2,
      polar: 2,
      positive: 1,
      negative: 1,
      other: 1,
    });
  });

  it("reports fractions that sum to one over a non-empty chain", () => {
    const total = classShares("AVSTKDX").reduce((s, x) => s + x.fraction, 0);
    expect(total).toBeCloseTo(1, 10);
  });

  it("keeps the sequence-panel legend order so the two agree", () => {
    expect(classShares("A").map((s) => s.cls)).toEqual([
      "hydrophobic",
      "polar",
      "positive",
      "negative",
      "other",
    ]);
  });

  it("divides by zero safely for an empty sequence", () => {
    expect(classShares("").every((s) => s.count === 0 && s.fraction === 0)).toBe(
      true,
    );
  });
});

describe("selectedInChain", () => {
  it("counts only this chain's own residues", () => {
    const selected = new Set(["A:1", "A:2", "B:1"]);
    expect(selectedInChain("A", 12, selected)).toBe(2);
    expect(selectedInChain("B", 4, selected)).toBe(1);
  });

  it("ignores a key beyond the chain's length", () => {
    // A stale key from a previously loaded structure must not inflate the
    // count for a shorter chain of the same label.
    expect(selectedInChain("A", 3, new Set(["A:1", "A:900"]))).toBe(1);
  });

  it("is zero for an empty selection", () => {
    expect(selectedInChain("A", 12, new Set())).toBe(0);
  });
});
