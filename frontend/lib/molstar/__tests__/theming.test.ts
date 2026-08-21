/**
 * Regression guard for the pLDDT colour inversion.
 *
 * ProteoLens renders pLDDT through Mol*'s `uncertainty` theme, which is really
 * a B-factor theme (see `COLOR_THEME`). Its scale is
 * `ColorScale.create({ reverse: true, domain: [0, 100], listOrName: 'red-white-blue' })`,
 * so under the *default* domain 0 is blue and 100 is red — correct for a
 * B-factor (low B = well ordered = blue), exactly backwards for pLDDT (high =
 * confident). On every AlphaFold import the confident core rendered red and the
 * disordered tails blue.
 *
 * The fix inverts the domain to `[100, 0]`. These tests pin that orientation
 * against the real Mol* colour scale, so flipping it back — or "tidying" the
 * endpoints into ascending order — fails here rather than in a screenshot.
 *
 * (Mol* is a trusted library and is not under test: what is asserted is the
 * colour OUR params produce from it.)
 */

import { describe, it, expect, vi } from "vitest";
import type { PluginContext } from "molstar/lib/mol-plugin/context";
import { Color, ColorScale } from "molstar/lib/mol-util/color";
import { UncertaintyColorThemeParams } from "molstar/lib/mol-theme/color/uncertainty";
import { ParamDefinition as PD } from "molstar/lib/mol-util/param-definition";

import { applyColoring } from "@/lib/molstar/actions";
import {
  COLORING_OPTIONS,
  COLOR_THEME,
  PLDDT_COLOR_DOMAIN,
  bfactorColumnSchemeFor,
  colorParamsFor,
  coloringOptionsFor,
} from "@/lib/molstar/theming";

const THEME_DEFAULTS = PD.getDefaultValues(UncertaintyColorThemeParams);

/** Rebuilds the scale `UncertaintyColorTheme` builds, for a given domain. */
function uncertaintyScale(domain: readonly [number, number]) {
  return ColorScale.create({
    reverse: true,
    domain: [domain[0], domain[1]],
    listOrName: THEME_DEFAULTS.list.colors,
  });
}

/** > 0 means the colour leans blue, < 0 means it leans red. */
function blueMinusRed(color: Color): number {
  const [r, , b] = Color.toRgb(color);
  return b - r;
}

describe("PLDDT_COLOR_DOMAIN", () => {
  it("is inverted — the high end comes first", () => {
    expect(PLDDT_COLOR_DOMAIN[0]).toBeGreaterThan(PLDDT_COLOR_DOMAIN[1]);
    expect([...PLDDT_COLOR_DOMAIN]).toEqual([100, 0]);
  });

  it("paints high pLDDT blue and low pLDDT red", () => {
    const scale = uncertaintyScale(PLDDT_COLOR_DOMAIN);
    // 90 = "very high" confidence in the AlphaFold banding, 20 = "very low".
    expect(blueMinusRed(scale.color(90))).toBeGreaterThan(0);
    expect(blueMinusRed(scale.color(20))).toBeLessThan(0);
    // ...and it is monotonic across the band boundaries, not just at the ends.
    expect(blueMinusRed(scale.color(90))).toBeGreaterThan(
      blueMinusRed(scale.color(70)),
    );
    expect(blueMinusRed(scale.color(70))).toBeGreaterThan(
      blueMinusRed(scale.color(50)),
    );
  });

  it("documents the bug: Mol*'s default domain paints high pLDDT RED", () => {
    // This is what shipped. If this assertion ever flips, Mol* changed the
    // theme's own orientation and `PLDDT_COLOR_DOMAIN` should be revisited
    // rather than blindly kept.
    const defaultScale = uncertaintyScale(THEME_DEFAULTS.domain);
    expect(blueMinusRed(defaultScale.color(90))).toBeLessThan(0);
    expect(blueMinusRed(defaultScale.color(20))).toBeGreaterThan(0);
  });
});

describe("colorParamsFor", () => {
  it("inverts the domain only for pLDDT on a structure that has pLDDT", () => {
    expect(colorParamsFor("plddt", true)).toEqual({ domain: PLDDT_COLOR_DOMAIN });
  });

  it("leaves the B-factor reading of the same theme alone", () => {
    // `plddt` and B-factor share the `uncertainty` theme. Inverting the domain
    // for an experimental structure would break B-factor colouring the exact
    // way the pLDDT bug broke pLDDT.
    expect(colorParamsFor("plddt", false)).toBeUndefined();
  });

  it("returns no params for every other scheme", () => {
    for (const [scheme] of COLORING_OPTIONS) {
      if (scheme === "plddt") continue;
      expect(colorParamsFor(scheme, true)).toBeUndefined();
      expect(colorParamsFor(scheme, false)).toBeUndefined();
    }
  });

  it("never gives `bfactor` the inverted domain", () => {
    // `bfactor` is the plain temperature-factor reading of the same theme, so
    // it must take Mol*'s default domain — low B = well ordered = blue. It
    // shares `uncertainty` with `plddt`, so the only thing keeping the two
    // apart is this branch; `hasPlddt` must not leak across it.
    expect(colorParamsFor("bfactor", false)).toBeUndefined();
    expect(colorParamsFor("bfactor", true)).toBeUndefined();
  });
});

describe("COLOR_THEME", () => {
  it("drives `bfactor` and `plddt` from the same uncertainty theme", () => {
    // One theme, two schemes: the difference is the domain, not the theme.
    expect(COLOR_THEME.bfactor).toBe("uncertainty");
    expect(COLOR_THEME.bfactor).toBe(COLOR_THEME.plddt);
  });
});

describe("coloringOptionsFor", () => {
  it("offers pLDDT when the B-factor column holds pLDDT", () => {
    expect(coloringOptionsFor(true).map(([v]) => v)).toContain("plddt");
  });

  it("hides pLDDT on a structure without it, keeping every other option", () => {
    const values = coloringOptionsFor(false).map(([v]) => v);
    expect(values).not.toContain("plddt");
    expect(values).toEqual(
      COLORING_OPTIONS.map(([v]) => v).filter((v) => v !== "plddt"),
    );
  });

  it("offers plain B-factor on an experimental structure", () => {
    // The regression this pins: gating the single shared option on `has_plddt`
    // left X-ray/NMR entries with no way to colour by B-factor at all.
    expect(coloringOptionsFor(false).map(([v]) => v)).toContain("bfactor");
  });

  it("hides plain B-factor on a predicted model", () => {
    // There the column is pLDDT, and "B-factor" would mislabel it.
    expect(coloringOptionsFor(true).map(([v]) => v)).not.toContain("bfactor");
  });

  it("offers exactly one of pLDDT / B-factor, never both and never neither", () => {
    for (const hasPlddt of [true, false]) {
      const values = coloringOptionsFor(hasPlddt).map(([v]) => v);
      const columnSchemes = values.filter(
        (v) => v === "plddt" || v === "bfactor",
      );
      expect(columnSchemes).toEqual([bfactorColumnSchemeFor(hasPlddt)]);
    }
  });

  it("drops exactly one option from the full menu", () => {
    expect(coloringOptionsFor(true)).toHaveLength(COLORING_OPTIONS.length - 1);
    expect(coloringOptionsFor(false)).toHaveLength(COLORING_OPTIONS.length - 1);
  });
});

/* -------------------------------------------------------------------------- */
/* applyColoring — the params actually handed to Mol*                          */
/* -------------------------------------------------------------------------- */

interface ThemeCall {
  color: string;
  colorParams?: { domain?: readonly [number, number] };
}

function fakePlugin() {
  const updateRepresentationsTheme = vi.fn();
  const components = [{ id: "component-1" }];
  const plugin = {
    managers: {
      structure: {
        hierarchy: { current: { structures: [{ components }] } },
        component: { updateRepresentationsTheme },
      },
    },
  } as unknown as PluginContext;
  return { plugin, updateRepresentationsTheme };
}

describe("applyColoring", () => {
  it("sends the inverted domain when the structure has pLDDT", () => {
    const { plugin, updateRepresentationsTheme } = fakePlugin();
    applyColoring(plugin, "plddt", { hasPlddt: true });

    expect(updateRepresentationsTheme).toHaveBeenCalledTimes(1);
    const params = updateRepresentationsTheme.mock.calls[0][1] as ThemeCall;
    expect(params.color).toBe(COLOR_THEME.plddt);
    expect(params.colorParams?.domain?.[0]).toBe(100);
    expect(params.colorParams?.domain?.[1]).toBe(0);
  });

  it("omits colorParams entirely when the structure has no pLDDT", () => {
    const { plugin, updateRepresentationsTheme } = fakePlugin();
    applyColoring(plugin, "plddt", { hasPlddt: false });

    const params = updateRepresentationsTheme.mock.calls[0][1] as ThemeCall;
    // Not `colorParams: undefined` — Mol* merges the key in and would clear
    // the theme's own defaults.
    expect("colorParams" in params).toBe(false);
  });

  it("renders `bfactor` on the theme's own domain, forwards", () => {
    const { plugin, updateRepresentationsTheme } = fakePlugin();
    applyColoring(plugin, "bfactor", { hasPlddt: false });

    const params = updateRepresentationsTheme.mock.calls[0][1] as ThemeCall;
    expect(params.color).toBe(COLOR_THEME.bfactor);
    // No domain override at all — anything else would paint a well-ordered
    // (low-B) atom red, the mirror image of the pLDDT bug.
    expect("colorParams" in params).toBe(false);
  });

  it("keeps `bfactor` on the default domain even if hasPlddt is true", () => {
    // The two schemes share `uncertainty`; only the scheme name may decide the
    // domain, so `hasPlddt` must not reach the `bfactor` branch.
    const { plugin, updateRepresentationsTheme } = fakePlugin();
    applyColoring(plugin, "bfactor", { hasPlddt: true });

    const params = updateRepresentationsTheme.mock.calls[0][1] as ThemeCall;
    expect("colorParams" in params).toBe(false);
  });

  it("passes plain themes through untouched", () => {
    const { plugin, updateRepresentationsTheme } = fakePlugin();
    applyColoring(plugin, "chain", { hasPlddt: true });

    const params = updateRepresentationsTheme.mock.calls[0][1] as ThemeCall;
    expect(params.color).toBe(COLOR_THEME.chain);
    expect("colorParams" in params).toBe(false);
  });
});
