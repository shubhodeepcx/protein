import { describe, it, expect } from "vitest";
import { alignmentBlocks, residueCount } from "@/lib/alignment-blocks";

/**
 * The numbering is the part a reader relies on: "which residue is this
 * mismatch?" is answered by the position printed beside the row, and a counter
 * that advanced on gap characters would answer it wrongly for every block after
 * the first indel — while still looking perfectly plausible.
 */

describe("alignmentBlocks", () => {
  it("numbers a gapless alignment straight through", () => {
    const blocks = alignmentBlocks("ACDEFG", "||||||", "ACDEFG", 3);
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toMatchObject({
      column: 0,
      rowA: "ACD",
      match: "|||",
      rowB: "ACD",
      startA: 1,
      endA: 3,
      startB: 1,
      endB: 3,
    });
    expect(blocks[1]).toMatchObject({
      column: 3,
      rowA: "EFG",
      startA: 4,
      endA: 6,
      startB: 4,
      endB: 6,
    });
  });

  it("advances each row's position on residues only, never on gaps", () => {
    //  columns:  0..2  |  3..5
    //  A row:    ACD   |  EFG   -> positions 1-3, then 4-6
    //  B row:    AC-   |  -FG   -> positions 1-2, then 3-4
    const blocks = alignmentBlocks("ACDEFG", "||   |", "AC--FG", 3);
    expect(blocks[0]).toMatchObject({ startA: 1, endA: 3, startB: 1, endB: 2 });
    expect(blocks[1]).toMatchObject({ startA: 4, endA: 6, startB: 3, endB: 4 });
  });

  it("advances the A row on residues only, symmetrically", () => {
    // The mirror of the case above. Gaps land on A when B is the longer
    // sequence — the ordinary predicted-vs-experimental direction, since the
    // full-length model is usually the one imported second.
    //  A row:    AC-   |  -FG   -> positions 1-2, then 3-4
    //  B row:    ACD   |  EFG   -> positions 1-3, then 4-6
    const blocks = alignmentBlocks("AC--FG", "||   |", "ACDEFG", 3);
    expect(blocks[0]).toMatchObject({ startA: 1, endA: 2, startB: 1, endB: 3 });
    expect(blocks[1]).toMatchObject({ startA: 3, endA: 4, startB: 4, endB: 6 });
  });

  it("reports null for a row that is entirely gaps in a block", () => {
    // A long insertion: B contributes no residue to the second block, so it
    // must not repeat the neighbouring position as if it did.
    const blocks = alignmentBlocks("ACDEFG", "||    ", "AC----", 3);
    expect(blocks[1].startB).toBeNull();
    expect(blocks[1].endB).toBeNull();
    // The A row in that same block is unaffected.
    expect(blocks[1]).toMatchObject({ startA: 4, endA: 6 });
  });

  it("resumes correct numbering after an all-gap block", () => {
    const blocks = alignmentBlocks("ACDEFGHI", "||    ||", "AC----HI", 2);
    expect(blocks.map((b) => [b.startB, b.endB])).toEqual([
      [1, 2],
      [null, null],
      [null, null],
      [3, 4],
    ]);
  });

  it("carries the match line through unchanged, blanks included", () => {
    const blocks = alignmentBlocks("ACDEFG", "||+  |", "ACKQWG", 6);
    expect(blocks[0].match).toBe("||+  |");
  });

  it("leaves a trailing partial block at its real width", () => {
    const blocks = alignmentBlocks("ACDEF", "|||||", "ACDEF", 3);
    expect(blocks[1].rowA).toBe("EF");
    expect(blocks[1].endA).toBe(5);
  });

  it("returns nothing for an empty alignment or a nonsensical width", () => {
    expect(alignmentBlocks("", "", "")).toEqual([]);
    expect(alignmentBlocks("ACDE", "||||", "ACDE", 0)).toEqual([]);
  });

  it("renders short rather than throwing when the rows disagree in length", () => {
    // A malformed payload should degrade, not crash the page.
    const blocks = alignmentBlocks("ACDEFG", "||", "AC", 3);
    expect(blocks).toHaveLength(2);
    expect(blocks[1].rowB).toBe("");
    expect(blocks[1].startB).toBeNull();
  });
});

describe("residueCount", () => {
  it("counts non-gap characters", () => {
    expect(residueCount("AC--DE")).toBe(4);
    expect(residueCount("----")).toBe(0);
  });
});
