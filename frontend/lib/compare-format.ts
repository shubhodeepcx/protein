/**
 * Number formatting for the comparison view (P7 / spec A3).
 *
 * Pure string functions, kept out of the components so they can be tested
 * without rendering. The whole point of the comparison table is that a reader
 * can tell at a glance which side has more of something, so the sign is never
 * dropped and zero is never dressed up as a small difference.
 */

/** U+2212 MINUS SIGN — aligns with digits, unlike the hyphen-minus. */
const MINUS = "−";

/** A signed delta, e.g. "+1,234", "−5", "0". Zero carries no sign. */
export function formatDelta(value: number, fractionDigits = 0): string {
  // -0 and +0 are both "no difference"; neither should print a sign.
  if (value === 0) return (0).toFixed(fractionDigits);
  const magnitude = Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
  return `${value > 0 ? "+" : MINUS}${magnitude}`;
}

/** A plain number with thousands separators, e.g. "1,234". */
export function formatNumber(value: number, fractionDigits = 0): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

/**
 * A 0-1 fraction as a percentage, e.g. 0.4565 -> "45.7%".
 *
 * Secondary structure arrives from the backend as fractions; percentages are
 * what the rest of the UI shows.
 */
export function formatFraction(value: number, fractionDigits = 1): string {
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

/** A signed 0-1 fraction delta in percentage points, e.g. "+4.6 pp". */
export function formatFractionDelta(value: number, fractionDigits = 1): string {
  const points = value * 100;
  // Round before testing for zero, so a delta that displays as 0.0 is not
  // given a sign it cannot justify at this precision.
  const rounded = Number(points.toFixed(fractionDigits));
  return `${formatDelta(rounded, fractionDigits)} pp`;
}

/** A signed percentage-point delta already expressed in points, e.g. "+1.20 pp". */
export function formatPointsDelta(value: number, fractionDigits = 2): string {
  const rounded = Number(value.toFixed(fractionDigits));
  return `${formatDelta(rounded, fractionDigits)} pp`;
}

/**
 * Tailwind text colour for a delta cell.
 *
 * Deliberately not red/green: neither direction is "good" — a bigger protein is
 * not a worse one — so a nonzero delta is simply emphasised and a zero is
 * dimmed. Colour carries "these differ", nothing more.
 */
export function deltaToneClass(value: number): string {
  return value === 0 ? "text-zinc-600" : "text-zinc-200";
}
