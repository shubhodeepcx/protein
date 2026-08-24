import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import {
  SecondaryStructureDonut,
  secondaryStructureSlices,
  NOT_ANNOTATED_LABEL,
} from "@/components/charts/secondary-structure-donut";
import type { SecondaryStructurePercentages } from "@/lib/types";

/**
 * The shipped defect: the backend has said `available: false` for files that
 * carry no secondary-structure assignment (every AlphaFold model) since the
 * flag was added, and the donut ignored it — drawing the placeholder
 * `helix 0 / sheet 0 / coil 1` split as a solid ring legended "Coil (100%)".
 * A reader cannot tell that apart from a genuinely all-disordered protein.
 *
 * These assertions are about the claim the chart makes, not its pixels.
 */

const measured: SecondaryStructurePercentages = {
  helix: 0.549,
  sheet: 0.059,
  coil: 0.392,
  available: true,
};

/** Exactly what the API returns for an AlphaFold model. */
const unannotated: SecondaryStructurePercentages = {
  helix: 0,
  sheet: 0,
  coil: 1,
  available: false,
};

afterEach(cleanup);

describe("secondaryStructureSlices", () => {
  it("returns one slice per structure type when the file declared them", () => {
    const slices = secondaryStructureSlices(measured);
    expect(slices.map((s) => s.name)).toEqual(["Helix", "Sheet", "Coil"]);
    expect(slices.map((s) => s.value)).toEqual([0.549, 0.059, 0.392]);
  });

  it("drops a type the structure has none of rather than drawing a zero slice", () => {
    const slices = secondaryStructureSlices({ ...measured, sheet: 0 });
    expect(slices.map((s) => s.name)).toEqual(["Helix", "Coil"]);
  });

  it("replaces the placeholder split with a single unlabelled ring when unavailable", () => {
    const slices = secondaryStructureSlices(unannotated);
    expect(slices).toHaveLength(1);
    expect(slices[0].name).toBe(NOT_ANNOTATED_LABEL);
  });

  it("never emits a Coil slice for a structure that declared nothing", () => {
    // The whole bug in one assertion: `coil: 1` must not reach the ring as
    // coil, because the file never said the protein was coil.
    const names = secondaryStructureSlices(unannotated).map((s) => s.name);
    expect(names).not.toContain("Coil");
  });

  it("does not colour the placeholder with any of the three data colours", () => {
    const dataColours = new Set(
      secondaryStructureSlices(measured).map((s) => s.fill),
    );
    const placeholder = secondaryStructureSlices(unannotated)[0];
    expect(dataColours.has(placeholder.fill)).toBe(false);
  });
});

describe("SecondaryStructureDonut", () => {
  it("warns that the split is a placeholder when the file declared none", () => {
    render(<SecondaryStructureDonut data={unannotated} />);
    const warning = screen.getByTestId("ss-unavailable-warning");
    expect(warning).toHaveTextContent(/declares no secondary structure/i);
    expect(warning).toHaveTextContent(/not a measurement/i);
  });

  it("stays silent when the structure really was annotated", () => {
    render(<SecondaryStructureDonut data={measured} />);
    expect(screen.queryByTestId("ss-unavailable-warning")).toBeNull();
  });

  it("does not warn merely because a protein is genuinely mostly coil", () => {
    // 100% coil with `available: true` is a real measurement — a warning here
    // would be the opposite error, and is what a naive `coil === 1` check does.
    render(
      <SecondaryStructureDonut
        data={{ helix: 0, sheet: 0, coil: 1, available: true }}
      />,
    );
    expect(screen.queryByTestId("ss-unavailable-warning")).toBeNull();
  });
});
