import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

import { ChainTree } from "@/components/chain-tree";
import { useStore } from "@/lib/store";
import type { ProteinSummary } from "@/lib/types";

const SUMMARY: ProteinSummary = {
  id: "test-id",
  source: "uploaded",
  source_id: null,
  name: "Crambin",
  organism: null,
  file_url: "/api/proteins/test-id/file",
  file_format: "pdb",
  chains: [
    { id: "test-id:A", label: "A", sequence: "TTCCPSIVARSN", residue_count: 12 },
    { id: "test-id:B", label: "B", sequence: "KRDE", residue_count: 4 },
  ],
  residue_count: 16,
  atom_count: 100,
  molecular_weight: 1234.5,
  has_plddt: false,
  warnings: [],
};

function resetStore(summary: ProteinSummary | null = SUMMARY) {
  useStore.setState({ current: summary, selected: new Set<string>() });
}

describe("ChainTree", () => {
  beforeEach(() => {
    cleanup();
    resetStore();
  });

  afterEach(() => {
    resetStore(null);
  });

  it("lists one row per chain with its label and residue count", () => {
    render(<ChainTree />);
    expect(screen.getByTestId("chain-select-A")).toHaveTextContent("A");
    expect(screen.getByTestId("chain-select-A")).toHaveTextContent("12 aa");
    expect(screen.getByTestId("chain-select-B")).toHaveTextContent("4 aa");
  });

  it("reports each chain's share of the structure", () => {
    render(<ChainTree />);
    // 12 of 16 residues, and 4 of 16.
    expect(screen.getByTestId("chain-select-A")).toHaveTextContent("75%");
    expect(screen.getByTestId("chain-select-B")).toHaveTextContent("25%");
  });

  it("summarises the structure in the header", () => {
    render(<ChainTree />);
    expect(screen.getByText(/2 chains · 16 aa/)).toBeInTheDocument();
  });

  it("selects every residue of a chain through the shared selection slice", () => {
    render(<ChainTree />);
    fireEvent.click(screen.getByTestId("chain-select-A"));

    const selected = useStore.getState().selected;
    expect(selected.size).toBe(12);
    expect(selected.has("A:1")).toBe(true);
    expect(selected.has("A:12")).toBe(true);
    // Chain B is untouched — `setSelection` replaces, it does not accumulate.
    expect(selected.has("B:1")).toBe(false);
  });

  it("replaces the selection when a second chain is clicked", () => {
    render(<ChainTree />);
    fireEvent.click(screen.getByTestId("chain-select-A"));
    fireEvent.click(screen.getByTestId("chain-select-B"));

    const selected = useStore.getState().selected;
    expect([...selected].sort()).toEqual(["B:1", "B:2", "B:3", "B:4"]);
  });

  it("shows how many of a chain's residues are currently selected", () => {
    render(<ChainTree />);
    // A selection made anywhere else — a 3D click, the sequence panel, the
    // `A:12` search box — has to show up here, because it is the same store.
    act(() => {
      useStore.getState().setSelection(["A:3", "A:4", "B:2"]);
    });
    expect(screen.getByTestId("chain-select-A")).toHaveTextContent("2 sel");
    expect(screen.getByTestId("chain-select-B")).toHaveTextContent("1 sel");
    expect(screen.getByTestId("chain-tree-selection-count")).toHaveTextContent(
      "3 selected",
    );
  });

  it("clears the selection from the rail", () => {
    render(<ChainTree />);
    fireEvent.click(screen.getByTestId("chain-select-A"));
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    expect(useStore.getState().selected.size).toBe(0);
  });

  it("offers no Clear control while nothing is selected", () => {
    render(<ChainTree />);
    expect(screen.queryByRole("button", { name: /clear/i })).toBeNull();
  });

  it("opens the rows by default on a structure with few chains", () => {
    // A monomer left every row collapsed, which is the empty rail this phase
    // exists to fix. Nothing is hidden at any chain count — this is only which
    // rows start open.
    render(<ChainTree />);
    expect(screen.getByTestId("chain-segment-A-1")).toBeInTheDocument();
    expect(screen.getByTestId("chain-segment-B-1")).toBeInTheDocument();
  });

  it("starts collapsed once there are more chains than the rail can show open", () => {
    resetStore({
      ...SUMMARY,
      chains: Array.from({ length: 5 }, (_, i) => ({
        id: `test-id:${i}`,
        label: String.fromCharCode(65 + i),
        sequence: "KRDE",
        residue_count: 4,
      })),
    });
    render(<ChainTree />);
    expect(screen.queryByTestId("chain-segment-A-1")).toBeNull();
    // ...and every chain is still listed; collapsing is not filtering.
    expect(screen.getAllByTestId(/^chain-select-/)).toHaveLength(5);

    fireEvent.click(screen.getByRole("button", { name: /expand chain A/i }));
    expect(screen.getByTestId("chain-segment-A-1")).toBeInTheDocument();
  });

  it("lets a row be collapsed again", () => {
    render(<ChainTree />);
    fireEvent.click(screen.getByRole("button", { name: /collapse chain A/i }));
    expect(screen.queryByTestId("chain-segment-A-1")).toBeNull();
  });

  it("selects exactly the residues of the segment that was clicked", () => {
    render(<ChainTree />);
    fireEvent.click(screen.getByTestId("chain-segment-B-1"));

    // Chain B is 4 residues, so its single segment is B:1–B:4.
    expect([...useStore.getState().selected].sort()).toEqual([
      "B:1",
      "B:2",
      "B:3",
      "B:4",
    ]);
  });

  it("collapses one chain without collapsing the other", () => {
    render(<ChainTree />);
    fireEvent.click(screen.getByRole("button", { name: /collapse chain A/i }));
    expect(screen.queryByTestId("chain-segment-A-1")).toBeNull();
    expect(screen.getByTestId("chain-segment-B-1")).toBeInTheDocument();
  });

  it("shows the per-class residue counts on an expanded row", () => {
    render(<ChainTree />);
    // KRDE — two positive (K, R), two negative (D, E), no hydrophobic.
    const positives = screen
      .getAllByText("Positive")
      .map((el) => el.closest("li"));
    // Chain A (TTCCPSIVARSN) has one positive residue, chain B (KRDE) two.
    expect(positives.map((li) => li?.textContent)).toEqual([
      "Positive1",
      "Positive2",
    ]);
  });

  it("says so plainly when a structure parsed with no chains", () => {
    resetStore({ ...SUMMARY, chains: [] });
    render(<ChainTree />);
    expect(screen.getByText(/No chains/i)).toBeInTheDocument();
  });

  it("renders the empty state rather than throwing with no protein loaded", () => {
    resetStore(null);
    render(<ChainTree />);
    expect(screen.getByText(/No chains/i)).toBeInTheDocument();
  });
});
