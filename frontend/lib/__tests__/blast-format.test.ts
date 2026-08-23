import { describe, it, expect } from "vitest";

import {
  formatCount,
  formatElapsed,
  formatEValue,
  formatPercent,
  queryCoverage,
} from "@/lib/blast-format";

describe("formatEValue", () => {
  it("keeps an exact zero as 0.0 rather than an em dash", () => {
    // BLAST reports 0.0 for a perfect self-hit. Rendering that as "—" would
    // read as "not reported", which is the opposite of what it means.
    expect(formatEValue(0)).toBe("0.0");
  });

  it("uses exponential notation for the very small values BLAST reports", () => {
    // Real values from the recorded EBI response. Fixed decimals would round
    // every one of these to 0.00.
    expect(formatEValue(5.5e-58)).toBe("5.5e-58");
    expect(formatEValue(2e-56)).toBe("2.0e-56");
  });

  it("uses plain decimals in the range where they are readable", () => {
    expect(formatEValue(0.024)).toBe("0.024");
    expect(formatEValue(1.8)).toBe("1.8");
    expect(formatEValue(10)).toBe("10");
  });

  it("returns an em dash only when the value really is absent", () => {
    expect(formatEValue(null)).toBe("—");
    expect(formatEValue(Number.NaN)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("shows one decimal so 32.6 and 32.3 stay distinguishable", () => {
    expect(formatPercent(32.6)).toBe("32.6%");
    expect(formatPercent(100)).toBe("100.0%");
  });

  it("distinguishes a missing value from zero", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0)).toBe("0.0%");
  });
});

describe("formatCount", () => {
  it("separates thousands", () => {
    expect(formatCount(3142)).toBe("3,142");
  });

  it("distinguishes a missing value from zero", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatCount(0)).toBe("0");
  });
});

describe("formatElapsed", () => {
  it("shows seconds alone under a minute", () => {
    expect(formatElapsed(0)).toBe("0s");
    expect(formatElapsed(45.4)).toBe("45s");
  });

  it("switches to minutes the moment there are any", () => {
    // "154s" reads as an error; "2m 34s" reads as a job that is working.
    expect(formatElapsed(60)).toBe("1m 0s");
    expect(formatElapsed(154)).toBe("2m 34s");
  });

  it("never renders a negative or non-finite duration", () => {
    expect(formatElapsed(-5)).toBe("0s");
    expect(formatElapsed(Number.NaN)).toBe("0s");
  });
});

describe("queryCoverage", () => {
  it("expresses the alignment length as a fraction of the query", () => {
    expect(queryCoverage(605, 605)).toBe(100);
    expect(queryCoverage(302.5, 605)).toBe(50);
  });

  it("returns null rather than inventing a number when an end is missing", () => {
    // Coverage is the statistic people use to DISMISS a hit. A made-up value
    // is worse than a blank.
    expect(queryCoverage(null, 605)).toBeNull();
    expect(queryCoverage(300, null)).toBeNull();
    expect(queryCoverage(300, 0)).toBeNull();
  });

  it("clamps an alignment longer than the query to 100%", () => {
    // Gapped alignments can exceed the query length; ">100% coverage" is
    // meaningless to a reader.
    expect(queryCoverage(700, 605)).toBe(100);
  });
});
