/**
 * Regression guard for the PAE colour-scale direction.
 *
 * PAE is an **error** in Angstroms — low is good. pLDDT is a **confidence** —
 * high is good. This codebase has already shipped one bug from exactly that
 * confusion: `PLDDT_COLOR_DOMAIN` in `lib/molstar/theming.ts` is inverted
 * on purpose because Mol*'s `uncertainty` theme runs the other way, and the
 * first version of it did not.
 *
 * A PAE scale applied backwards produces a picture that is fully plausible and
 * fully wrong: the confidently placed domain core reads as the uncertain part.
 * These tests pin the direction by **luminance**, not by hex values, so a
 * palette tweak stays free while an inversion fails.
 */

import { describe, it, expect } from "vitest";
import {
  PAE_COLOR_RAMP,
  PAE_CONFIDENT_ANGSTROMS,
  PLDDT_BAND_COLORS,
  paeColor,
  paeLegendTicks,
  relativeLuminance,
  rgbCss,
  summarisePae,
} from "@/lib/pae-scale";

const MAX = 31.75; // AlphaFold's own ceiling for AF-P01308-F1.

describe("paeColor direction", () => {
  it("paints low error dark and high error pale, the AlphaFold DB convention", () => {
    const best = relativeLuminance(paeColor(0, MAX));
    const worst = relativeLuminance(paeColor(MAX, MAX));
    expect(best).toBeLessThan(worst);
  });

  it("is monotonic in luminance across the whole range", () => {
    // Every step must go the same way. A ramp that dips in the middle would
    // make two different errors look equally bad.
    const samples = Array.from({ length: 33 }, (_, i) =>
      relativeLuminance(paeColor((MAX * i) / 32, MAX)),
    );
    for (let i = 1; i < samples.length; i += 1) {
      expect(samples[i]).toBeGreaterThan(samples[i - 1]);
    }
  });

  it("keeps the low-error end distinguishable from the dark panel background", () => {
    // zinc-900 (#18181b) is the card the heatmap sits on. A 0 A cell that
    // matched it would render a well-predicted protein as an empty square.
    const zinc900 = relativeLuminance({ r: 24, g: 24, b: 27 });
    expect(relativeLuminance(paeColor(0, MAX))).toBeGreaterThan(zinc900 * 2);
  });

  it("anchors the scale to the entry's own max_error, not a constant", () => {
    // The same 10 A must not look the same on two proteins with different
    // ceilings — the legend prints the ceiling, so the ramp has to use it.
    const onNarrow = relativeLuminance(paeColor(10, 10));
    const onWide = relativeLuminance(paeColor(10, 30));
    expect(onNarrow).toBeGreaterThan(onWide);
  });

  it("clamps out-of-range values instead of running off the ramp", () => {
    expect(paeColor(-5, MAX)).toEqual(paeColor(0, MAX));
    expect(paeColor(MAX * 3, MAX)).toEqual(paeColor(MAX, MAX));
  });

  it("survives a zero or non-finite ceiling", () => {
    expect(paeColor(5, 0)).toEqual(PAE_COLOR_RAMP[0]);
    expect(paeColor(5, Number.NaN)).toEqual(PAE_COLOR_RAMP[0]);
  });

  it("renders as a css rgb() triple", () => {
    expect(rgbCss({ r: 1, g: 2, b: 3 })).toBe("rgb(1, 2, 3)");
  });
});

describe("relativeLuminance", () => {
  it("matches the WCAG definition at the ends and in the middle", () => {
    // The direction tests above are only as trustworthy as this function. A
    // luminance that dropped the sRGB transfer curve would still rank the ramp
    // correctly today and quietly mis-rank a future palette, so pin it against
    // the published values rather than against itself.
    expect(relativeLuminance({ r: 255, g: 255, b: 255 })).toBeCloseTo(1, 6);
    expect(relativeLuminance({ r: 0, g: 0, b: 0 })).toBeCloseTo(0, 6);
    // Mid grey #808080 is 0.2159 under the sRGB curve, and would be 0.5019
    // without it.
    expect(relativeLuminance({ r: 128, g: 128, b: 128 })).toBeCloseTo(0.2159, 3);
    // Pure green carries most of the weight; pure blue almost none.
    expect(relativeLuminance({ r: 0, g: 255, b: 0 })).toBeCloseTo(0.7152, 4);
    expect(relativeLuminance({ r: 0, g: 0, b: 255 })).toBeCloseTo(0.0722, 4);
  });
});

describe("summarisePae", () => {
  it("reports median, worst and the confidently-placed share", () => {
    const values = [
      [0, 1, 2],
      [1, 0, 30],
      [2, 30, 0],
    ];
    const summary = summarisePae(values);
    expect(summary.cellCount).toBe(9);
    expect(summary.median).toBe(1);
    expect(summary.worst).toBe(30);
    // Seven of nine cells are under 5 A.
    expect(summary.confidentFraction).toBeCloseTo(7 / 9, 5);
  });

  it("averages the two middle cells for an even count", () => {
    expect(summarisePae([[1, 2, 3, 10]]).median).toBe(2.5);
  });

  it("does not mutate the caller's matrix", () => {
    // The median needs a sort; sorting the response in place would scramble
    // the rows the heatmap then paints.
    const values = [[9, 1, 5]];
    summarisePae(values);
    expect(values).toEqual([[9, 1, 5]]);
  });

  it("returns zeroes for an empty matrix rather than NaN", () => {
    expect(summarisePae([])).toEqual({
      cellCount: 0,
      median: 0,
      worst: 0,
      confidentFraction: 0,
    });
  });

  it("counts a cell exactly at the confident threshold as not confident", () => {
    expect(summarisePae([[PAE_CONFIDENT_ANGSTROMS]]).confidentFraction).toBe(0);
    expect(
      summarisePae([[PAE_CONFIDENT_ANGSTROMS - 0.01]]).confidentFraction,
    ).toBe(1);
  });
});

describe("paeLegendTicks", () => {
  it("spans 0 to the ceiling inclusive", () => {
    expect(paeLegendTicks(30, 4)).toEqual([0, 10, 20, 30]);
  });

  it("degrades to a single zero tick for a missing ceiling", () => {
    expect(paeLegendTicks(0)).toEqual([0]);
    expect(paeLegendTicks(Number.NaN)).toEqual([0]);
  });
});

describe("PLDDT_BAND_COLORS", () => {
  it("uses AlphaFold's own band colours, blue for confident", () => {
    // Same convention as the structure colouring in `lib/molstar/theming.ts`:
    // blue is confident, orange is not. Swapping these would contradict the
    // 3D view sitting next to this chart.
    expect(PLDDT_BAND_COLORS.very_high).toBe("#0053d6");
    expect(PLDDT_BAND_COLORS.confident).toBe("#65cbf3");
    expect(PLDDT_BAND_COLORS.low).toBe("#ffdb13");
    expect(PLDDT_BAND_COLORS.very_low).toBe("#ff7d45");
  });

  it("orders bands so confidence gets bluer, not warmer", () => {
    const blueness = (hex: string) => {
      const b = parseInt(hex.slice(5, 7), 16);
      const r = parseInt(hex.slice(1, 3), 16);
      return b - r;
    };
    expect(blueness(PLDDT_BAND_COLORS.very_high)).toBeGreaterThan(
      blueness(PLDDT_BAND_COLORS.low),
    );
    expect(blueness(PLDDT_BAND_COLORS.confident)).toBeGreaterThan(
      blueness(PLDDT_BAND_COLORS.very_low),
    );
  });
});
