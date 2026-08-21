import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";

import { ViewerControls } from "@/components/viewer-controls";
import { useStore } from "@/lib/store";

function optionLabels(): string[] {
  const select = screen.getByLabelText("Coloring") as HTMLSelectElement;
  return Array.from(select.options).map((o) => o.textContent ?? "");
}

describe("ViewerControls — B-factor column gating", () => {
  beforeEach(() => {
    act(() => {
      useStore.setState({ coloring: "chain", representation: "cartoon" });
    });
  });

  afterEach(cleanup);

  it("offers pLDDT colouring when the structure carries pLDDT", () => {
    render(<ViewerControls hasPlddt />);
    expect(optionLabels()).toContain("pLDDT confidence");
  });

  it("hides pLDDT colouring on a structure without it", () => {
    // The bug this pins: `has_plddt` reached the API and lib/types.ts but never
    // the UI, so an X-ray entry advertised a confidence score it does not have.
    render(<ViewerControls />);
    expect(optionLabels()).not.toContain("pLDDT confidence");
    // Every other scheme is still offered — this gates one option, not the menu.
    expect(optionLabels()).toEqual(
      expect.arrayContaining([
        "Chain",
        "Secondary structure",
        "Hydrophobicity",
        "Residue type",
      ]),
    );
  });

  it("falls back to chain colouring when a stale pLDDT selection is carried in", () => {
    // `coloring` is store state and survives navigation, so leaving an
    // AlphaFold model on pLDDT and opening an X-ray entry would bind the select
    // to a value it no longer lists.
    act(() => {
      useStore.setState({ coloring: "plddt" });
    });
    render(<ViewerControls />);
    expect(useStore.getState().coloring).toBe("chain");
    expect((screen.getByLabelText("Coloring") as HTMLSelectElement).value).toBe(
      "chain",
    );
  });

  it("keeps a pLDDT selection when the structure does have pLDDT", () => {
    act(() => {
      useStore.setState({ coloring: "plddt" });
    });
    render(<ViewerControls hasPlddt />);
    expect(useStore.getState().coloring).toBe("plddt");
  });

  it("offers B-factor colouring on a structure without pLDDT", () => {
    // The regression this pins: one option served both readings of the
    // B-factor column, so gating it on `has_plddt` took B-factor colouring of
    // experimental structures away entirely.
    render(<ViewerControls />);
    expect(optionLabels()).toContain("B-factor");
  });

  it("offers exactly one of pLDDT / B-factor either way", () => {
    render(<ViewerControls hasPlddt />);
    expect(optionLabels()).toEqual(
      expect.arrayContaining(["pLDDT confidence"]),
    );
    expect(optionLabels()).not.toContain("B-factor");

    cleanup();

    render(<ViewerControls />);
    expect(optionLabels()).toContain("B-factor");
    expect(optionLabels()).not.toContain("pLDDT confidence");
  });

  it("falls back to chain colouring when a stale B-factor selection is carried in", () => {
    // The mirror of the stale-pLDDT case: "B-factor" mislabels a pLDDT column,
    // so it is not listed for a predicted model and must not stay selected.
    act(() => {
      useStore.setState({ coloring: "bfactor" });
    });
    render(<ViewerControls hasPlddt />);
    expect(useStore.getState().coloring).toBe("chain");
    expect((screen.getByLabelText("Coloring") as HTMLSelectElement).value).toBe(
      "chain",
    );
  });

  it("keeps a B-factor selection on a structure without pLDDT", () => {
    act(() => {
      useStore.setState({ coloring: "bfactor" });
    });
    render(<ViewerControls />);
    expect(useStore.getState().coloring).toBe("bfactor");
  });
});
