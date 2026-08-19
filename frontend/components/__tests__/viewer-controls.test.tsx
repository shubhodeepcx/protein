import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";

import { ViewerControls } from "@/components/viewer-controls";
import { useStore } from "@/lib/store";

function optionLabels(): string[] {
  const select = screen.getByLabelText("Coloring") as HTMLSelectElement;
  return Array.from(select.options).map((o) => o.textContent ?? "");
}

describe("ViewerControls — pLDDT gating", () => {
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
});
