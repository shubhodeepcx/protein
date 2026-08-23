import { describe, it, expect } from "vitest";
import {
  deltaToneClass,
  formatDelta,
  formatFraction,
  formatFractionDelta,
  formatNumber,
  formatPointsDelta,
} from "@/lib/compare-format";

/** U+2212 MINUS SIGN — what the formatters emit, not a hyphen. */
const MINUS = "−";

describe("formatDelta", () => {
  it("signs a positive delta and thousands-separates it", () => {
    expect(formatDelta(1234)).toBe("+1,234");
  });

  it("uses a true minus sign for negatives", () => {
    expect(formatDelta(-5)).toBe(`${MINUS}5`);
    expect(formatDelta(-5)).not.toContain("-");
  });

  it("gives zero no sign at all", () => {
    // The table's whole job is "which side has more"; a signed zero would
    // claim a direction the number does not have.
    expect(formatDelta(0)).toBe("0");
    expect(formatDelta(-0)).toBe("0");
  });

  it("honours the requested precision on both sides of zero", () => {
    expect(formatDelta(12.345, 1)).toBe("+12.3");
    expect(formatDelta(-12.345, 1)).toBe(`${MINUS}12.3`);
    expect(formatDelta(0, 2)).toBe("0.00");
  });
});

describe("formatNumber", () => {
  it("separates thousands and keeps the requested precision", () => {
    expect(formatNumber(4736.43, 1)).toBe("4,736.4");
    expect(formatNumber(327)).toBe("327");
  });
});

describe("formatFraction", () => {
  it("renders a 0-1 fraction as a percentage", () => {
    // Crambin's real split, as the analytics endpoint returns it.
    expect(formatFraction(0.4567)).toBe("45.7%");
    expect(formatFraction(0.1739)).toBe("17.4%");
    expect(formatFraction(0)).toBe("0.0%");
    expect(formatFraction(1)).toBe("100.0%");
  });

  it("respects an explicit precision", () => {
    expect(formatFraction(0.4567, 2)).toBe("45.67%");
    expect(formatFraction(0.4567, 0)).toBe("46%");
  });
});

describe("formatFractionDelta", () => {
  it("converts a fraction delta to signed percentage points", () => {
    expect(formatFractionDelta(0.0456)).toBe("+4.6 pp");
    expect(formatFractionDelta(-0.0456)).toBe(`${MINUS}4.6 pp`);
  });

  it("drops the sign when the delta rounds away at the displayed precision", () => {
    // 0.0004 is +0.04 pp, which prints as "0.0". Showing "+0.0 pp" would claim
    // a direction the reader cannot see and cannot check.
    expect(formatFractionDelta(0.0004)).toBe("0.0 pp");
  });
});

describe("formatPointsDelta", () => {
  it("signs a delta already expressed in percentage points", () => {
    expect(formatPointsDelta(1.2)).toBe("+1.20 pp");
    expect(formatPointsDelta(-1.2)).toBe(`${MINUS}1.20 pp`);
    expect(formatPointsDelta(0)).toBe("0.00 pp");
  });

  it("drops the sign when the delta rounds away", () => {
    expect(formatPointsDelta(0.001)).toBe("0.00 pp");
  });
});

describe("deltaToneClass", () => {
  it("dims zero and emphasises any difference", () => {
    expect(deltaToneClass(0)).toBe("text-zinc-600");
    expect(deltaToneClass(1)).toBe("text-zinc-200");
    expect(deltaToneClass(-1)).toBe("text-zinc-200");
  });

  it("does not colour by direction", () => {
    // Neither direction is "good" — a bigger protein is not a worse one — so
    // positive and negative must look the same.
    expect(deltaToneClass(5)).toBe(deltaToneClass(-5));
  });
});
