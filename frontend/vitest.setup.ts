import "@testing-library/jest-dom/vitest";

/**
 * jsdom ships no `ResizeObserver`, and Recharts' `ResponsiveContainer`
 * constructs one on mount. Without this stub every chart component throws at
 * render time and could only be tested through its pure helpers — which is
 * part of why the `secondary_structure.available` bug stayed invisible to the
 * suite for as long as it did.
 *
 * The stub reports nothing, so charts render at zero size. That is fine: the
 * assertions around them are about the claims the chart makes, never its SVG
 * geometry.
 */
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}
