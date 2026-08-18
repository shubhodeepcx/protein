import { describe, it, expect } from "vitest";
import {
  parseResidueQuery,
  parseResidueKey,
  residueClass,
  residueKey,
  RESIDUE_CLASS_ORDER,
  RESIDUE_CLASS_TEXT,
  findIndexDrift,
  type QueryChain,
} from "@/lib/residue";

const CHAINS: QueryChain[] = [
  { label: "A", residue_count: 46 },
  { label: "B", residue_count: 12 },
];

describe("parseResidueQuery", () => {
  it("parses a valid A:123-style query", () => {
    const result = parseResidueQuery("A:12", CHAINS);
    expect(result).toEqual({ ok: true, key: "A:12", chain: "A", position: 12 });
  });

  it("accepts the first and last residue of a chain", () => {
    expect(parseResidueQuery("A:1", CHAINS)).toMatchObject({ ok: true, key: "A:1" });
    expect(parseResidueQuery("A:46", CHAINS)).toMatchObject({ ok: true, key: "A:46" });
  });

  it("accepts a lowercase chain letter and normalises it to the real label", () => {
    expect(parseResidueQuery("b:3", CHAINS)).toEqual({
      ok: true,
      key: "B:3",
      chain: "B",
      position: 3,
    });
  });

  it("tolerates surrounding and inner whitespace", () => {
    expect(parseResidueQuery("  A : 7  ", CHAINS)).toMatchObject({
      ok: true,
      key: "A:7",
    });
  });

  it("rejects an unknown chain and lists what is available", () => {
    const result = parseResidueQuery("Z:1", CHAINS);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("No chain Z");
      expect(result.error).toContain("A, B");
    }
  });

  it("rejects an out-of-range residue number with the chain's real length", () => {
    const result = parseResidueQuery("A:999", CHAINS);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBe(
        "No residue A:999 — chain A has 46 residues",
      );
    }
  });

  it("rejects position 0 (the panel is 1-based)", () => {
    expect(parseResidueQuery("A:0", CHAINS).ok).toBe(false);
  });

  it("rejects malformed input: no colon", () => {
    const result = parseResidueQuery("A12", CHAINS);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("chain:residue");
  });

  it("rejects malformed input: non-numeric residue", () => {
    expect(parseResidueQuery("A:abc", CHAINS).ok).toBe(false);
  });

  it("rejects an empty query", () => {
    expect(parseResidueQuery("   ", CHAINS).ok).toBe(false);
  });

  it("reports a structure with no chains rather than throwing", () => {
    const result = parseResidueQuery("A:1", []);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("no chains");
  });
});

describe("residueKey / parseResidueKey", () => {
  it("round-trips a key", () => {
    expect(parseResidueKey(residueKey("A", 12))).toEqual({
      chain: "A",
      position: 12,
    });
  });

  it("returns null for malformed keys", () => {
    for (const bad of ["", "A", "A:", ":12", "A:x", "A:-3", "A:1.5"]) {
      expect(parseResidueKey(bad)).toBeNull();
    }
  });
});

describe("residueClass", () => {
  it("classifies the standard 20 into the four documented groups", () => {
    for (const aa of "AVLIMFWP") expect(residueClass(aa)).toBe("hydrophobic");
    for (const aa of "STNQGCY") expect(residueClass(aa)).toBe("polar");
    for (const aa of "KRH") expect(residueClass(aa)).toBe("positive");
    for (const aa of "DE") expect(residueClass(aa)).toBe("negative");
  });

  it("covers all 20 standard residues exactly once", () => {
    const standard = "AVLIMFWPSTNQGCYKRHDE";
    expect(new Set(standard).size).toBe(20);
    for (const aa of standard) expect(residueClass(aa)).not.toBe("other");
  });

  it("maps the parser's X placeholder and anything unknown to 'other'", () => {
    expect(residueClass("X")).toBe("other");
    expect(residueClass("Z")).toBe("other");
    expect(residueClass("")).toBe("other");
    expect(residueClass("AL")).toBe("other");
  });

  it("is case-insensitive", () => {
    expect(residueClass("a")).toBe("hydrophobic");
  });

  it("has a distinct colour for every class in the legend", () => {
    const colors = RESIDUE_CLASS_ORDER.map((c) => RESIDUE_CLASS_TEXT[c]);
    expect(new Set(colors).size).toBe(RESIDUE_CLASS_ORDER.length);
  });
});

describe("findIndexDrift", () => {
  const index = {
    keyToResidue: new Map<string, number>(),
    residueToKey: new Map<number, string>(),
    chainCounts: new Map([
      ["A", 46],
      ["B", 12],
    ]),
  };

  it("reports nothing when Mol* and the API agree", () => {
    expect(findIndexDrift(index, CHAINS)).toEqual([]);
  });

  it("reports a chain whose counts disagree", () => {
    const drift = findIndexDrift(index, [{ label: "A", residue_count: 45 }]);
    expect(drift).toHaveLength(1);
    expect(drift[0]).toContain("Mol* has 46 residues, API reported 45");
  });

  it("reports a chain missing from the loaded structure", () => {
    const drift = findIndexDrift(index, [{ label: "C", residue_count: 3 }]);
    expect(drift).toEqual(["chain C: absent from the loaded structure"]);
  });
});
