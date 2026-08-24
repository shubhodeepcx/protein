/**
 * Display formatting for BLAST statistics (P8).
 *
 * Kept out of the components because these are the numbers a biologist reads
 * first, and getting one wrong — an E-value rounded to "0" when it is 0.024,
 * say — silently changes what the table means.
 */

/**
 * An E-value the way BLAST output writes it.
 *
 * BLAST reports E-values spanning ~1e-180 to ~10, so no single fixed-decimal
 * format works: 5.5e-58 rounds to "0.00" and 0.0 must stay "0.0". The rule is
 * the one BLAST's own text output uses — exponential outside the range where
 * decimals are readable, plain decimals inside it.
 */
export function formatEValue(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  if (value === 0) return "0.0";
  const magnitude = Math.abs(value);
  if (magnitude < 1e-3 || magnitude >= 1e4) {
    return value.toExponential(1).replace("e+", "e");
  }
  // 3 significant digits keeps 0.024 and 1.35 both readable.
  return Number(value.toPrecision(3)).toString();
}

/** A percentage with one decimal, or an em dash when it was not reported. */
export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)}%`;
}

/** An integer with thousands separators, or an em dash. */
export function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US");
}

/**
 * Elapsed wall-clock time, for the progress line.
 *
 * Minutes appear as soon as there are any, because "154s" reads as an error
 * and "2m 34s" reads as a job that is working.
 */
export function formatElapsed(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0s";
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

/**
 * How much of the query an alignment covers, as a percentage.
 *
 * Returns null rather than a wrong number when either end is missing —
 * coverage is the statistic people use to dismiss a hit, so a made-up value
 * here is worse than a blank.
 */
export function queryCoverage(
  alignLength: number | null,
  queryLength: number | null,
): number | null {
  if (alignLength === null || queryLength === null || queryLength <= 0) return null;
  return Math.min(100, (alignLength / queryLength) * 100);
}
