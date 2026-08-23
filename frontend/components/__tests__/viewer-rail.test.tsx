import React from "react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { ViewerRail } from "@/components/viewer-rail";
import { useStore } from "@/lib/store";

/**
 * The rail's tab list is the only place a whole panel can go missing without
 * any panel test noticing — the panel keeps passing its own tests while being
 * unreachable. This file pins the set of tabs.
 */
describe("ViewerRail", () => {
  beforeEach(() => {
    act(() => {
      useStore.setState({
        current: null,
        annotations: null,
        analytics: null,
        similar: null,
        loadAnnotations: async () => {},
        loadAnalytics: async () => {},
        loadSimilar: async () => {},
        resumeBlast: async () => {},
      });
    });
  });
  afterEach(cleanup);

  it("offers every panel the viewer ships", () => {
    render(<ViewerRail proteinId="abc123" />);

    for (const tab of [
      "Overview",
      "Sequence",
      "Analytics",
      "Annotations",
      "Similarity",
    ]) {
      expect(screen.getByRole("tab", { name: tab })).toBeInTheDocument();
    }
  });

  it("wires the Similarity tab to the Similarity panel", async () => {
    // A trigger with no matching content is a tab that opens onto nothing —
    // and every panel-level test still passes while it does.
    render(<ViewerRail proteinId="abc123" />);

    fireEvent.click(screen.getByRole("tab", { name: "Similarity" }));

    expect(
      await screen.findByRole("button", { name: /Run blastp at EBI/ }),
    ).toBeInTheDocument();
  });

  it("opens on Overview so nothing is fetched before it is asked for", () => {
    // Similarity and Annotations both hit the network on mount; making either
    // the default tab would turn opening a structure into an external call.
    render(<ViewerRail proteinId="abc123" />);

    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Similarity" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });
});
