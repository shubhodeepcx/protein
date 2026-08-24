/**
 * Colour scale and summary statistics for the Predicted Aligned Error heatmap.
 *
 * ## Direction, and why it is the load-bearing part
 *
 * PAE is an **error** measured in Angstroms: cell (i, j) is the expected error
 * in residue j's position when the prediction is aligned on residue i. **Low is
 * good.** pLDDT, which this codebase already colours structures by, is a
 * **confidence**: high is good. The two run in opposite directions, and a scale
 * applied the wrong way round produces a picture that is entirely plausible and
 * entirely inverted — the exact bug that shipped once with `PLDDT_COLOR_DOMAIN`
 * (see `lib/molstar/theming.ts`, where the inverted domain is deliberate).
 *
 * The scale here follows **AlphaFold DB's own PAE plot**: dark green for low
 * error, pale for high error. Matching the convention a reader already knows
 * from an AFDB entry page is worth more than internal consistency with the
 * pLDDT ramp, because PAE and pLDDT genuinely are opposite quantities and
 * making them look alike would be the real hazard.
 *
 * Every channel of the ramp increases monotonically from the low-error stop to
 * the high-error stop, so luminance rises with error. `paeColorRamp` is pinned
 * by a monotonicity test — flipping the stops fails it.
 *
 * The heatmap never relies on colour alone: `summarisePae` produces the numbers
 * the panel states in words next to it.
 */

export interface Rgb {
  readonly r: number;
  readonly g: number;
  readonly b: number;
}

/**
 * The ramp, low error first.
 *
 * emerald-800 -> emerald-400 -> emerald-50. Deliberately not starting at pure
 * black: the low-error end has to stay distinguishable from the panel
 * background in the dark theme, or a well-predicted protein would render as an
 * empty square.
 */
export const PAE_COLOR_RAMP: readonly Rgb[] = [
  { r: 6, g: 95, b: 70 }, // 0 A — confidently placed
  { r: 52, g: 211, b: 153 },
  { r: 236, g: 253, b: 245 }, // max A — position uncertain
];

/**
 * Below this many Angstroms, two residues' relative position is conventionally
 * treated as well defined. Used only for the plain-language summary, never to
 * threshold the picture itself.
 */
export const PAE_CONFIDENT_ANGSTROMS = 5;

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Clamp `value` into [0, 1]. */
function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return value < 0 ? 0 : value > 1 ? 1 : value;
}

/**
 * The colour for one PAE value, in Angstroms.
 *
 * `maxError` is AlphaFold's own ceiling for the entry, carried on the wire, so
 * the scale is anchored to the same number the legend prints rather than being
 * silently rescaled per protein.
 */
export function paeColor(value: number, maxError: number): Rgb {
  const t = clamp01(maxError > 0 ? value / maxError : 0);
  const spans = PAE_COLOR_RAMP.length - 1;
  const scaled = t * spans;
  const index = Math.min(Math.floor(scaled), spans - 1);
  const local = scaled - index;
  const from = PAE_COLOR_RAMP[index];
  const to = PAE_COLOR_RAMP[index + 1];
  return {
    r: Math.round(lerp(from.r, to.r, local)),
    g: Math.round(lerp(from.g, to.g, local)),
    b: Math.round(lerp(from.b, to.b, local)),
  };
}

export function rgbCss({ r, g, b }: Rgb): string {
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * WCAG relative luminance. Used by the direction test, not by rendering.
 *
 * Luminance is the property that makes the scale's direction checkable without
 * asserting exact hex values, which would break on any palette tweak while
 * leaving an inverted ramp undetected.
 */
export function relativeLuminance({ r, g, b }: Rgb): number {
  const channel = (raw: number): number => {
    const c = raw / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export interface PaeSummary {
  /** Cells in the binned matrix. */
  cellCount: number;
  /** Median PAE across every cell, in Angstroms. */
  median: number;
  /** Worst PAE in the matrix, in Angstroms. */
  worst: number;
  /** Share of cells under `PAE_CONFIDENT_ANGSTROMS`, 0-1. */
  confidentFraction: number;
}

/**
 * The numbers the panel states in words beside the heatmap.
 *
 * This is what keeps the message from depending on colour: a reader who cannot
 * separate the greens still gets "median 12.4 A, worst 31.8 A, 34% of residue
 * pairs confidently placed".
 */
export function summarisePae(values: readonly (readonly number[])[]): PaeSummary {
  const flat: number[] = [];
  for (const row of values) for (const cell of row) flat.push(cell);
  if (flat.length === 0) {
    return { cellCount: 0, median: 0, worst: 0, confidentFraction: 0 };
  }
  flat.sort((a, b) => a - b);
  const mid = Math.floor(flat.length / 2);
  const median =
    flat.length % 2 === 1 ? flat[mid] : (flat[mid - 1] + flat[mid]) / 2;
  const confident = flat.filter((v) => v < PAE_CONFIDENT_ANGSTROMS).length;
  return {
    cellCount: flat.length,
    median,
    worst: flat[flat.length - 1],
    confidentFraction: confident / flat.length,
  };
}

/**
 * Evenly spaced Angstrom ticks for the legend, from 0 to `maxError` inclusive.
 *
 * The legend prints real Angstrom numbers rather than "low/high", so the scale
 * says what it measures.
 */
export function paeLegendTicks(maxError: number, count = 4): number[] {
  if (!Number.isFinite(maxError) || maxError <= 0 || count < 2) return [0];
  const ticks: number[] = [];
  for (let i = 0; i < count; i += 1) {
    ticks.push((maxError * i) / (count - 1));
  }
  return ticks;
}

/**
 * Official AlphaFold DB band colours, so the band chart matches both the
 * AlphaFold entry page and the structure colouring already shipped in the
 * viewer (`lib/molstar/theming.ts`): blue is confident, orange is not.
 */
export const PLDDT_BAND_COLORS: Readonly<Record<string, string>> = {
  very_high: "#0053d6",
  confident: "#65cbf3",
  low: "#ffdb13",
  very_low: "#ff7d45",
};
