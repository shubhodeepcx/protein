import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
  act,
} from "@testing-library/react";

import { SequencePanel } from "@/components/sequence-panel";
import { useStore } from "@/lib/store";
import type { ProteinSummary } from "@/lib/types";

// jsdom does not implement scrollIntoView; the panel calls it optionally, but
// stubbing it lets us assert the scroll-to-selected behaviour.
const scrollIntoView = vi.fn();

const SUMMARY: ProteinSummary = {
  id: "test-id",
  source: "uploaded",
  source_id: null,
  name: "Crambin",
  organism: null,
  file_url: "/api/proteins/test-id/file",
  file_format: "pdb",
  chains: [
    // 12 residues so the grid wraps onto a second row (10 per row).
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

describe("SequencePanel", () => {
  beforeEach(() => {
    cleanup();
    scrollIntoView.mockReset();
    Element.prototype.scrollIntoView = scrollIntoView;
    resetStore();
  });

  afterEach(() => {
    resetStore(null);
  });

  it("renders one block per chain with its residue count", () => {
    render(<SequencePanel />);
    expect(screen.getByText("Chain A")).toBeInTheDocument();
    expect(screen.getByText("Chain B")).toBeInTheDocument();
    expect(screen.getByText("12 residues")).toBeInTheDocument();
    expect(screen.getByText("4 residues")).toBeInTheDocument();
  });

  it("renders a clickable cell per residue, keyed 1-based within the chain", () => {
    render(<SequencePanel />);
    // 12 + 4 residue buttons.
    expect(screen.getAllByRole("button", { name: /^Residue [AB]:\d+$/ })).toHaveLength(16);
    expect(screen.getByRole("button", { name: "Residue A:1" })).toHaveTextContent("T");
    expect(screen.getByRole("button", { name: "Residue A:12" })).toHaveTextContent("N");
    // Chain B restarts at 1 — numbering is per-chain, not global.
    expect(screen.getByRole("button", { name: "Residue B:1" })).toHaveTextContent("K");
  });

  it("shows a position ruler every 10 residues", () => {
    render(<SequencePanel />);
    const chainA = screen.getByText("Chain A").parentElement!.parentElement!;
    expect(within(chainA).getByText("1")).toBeInTheDocument();
    expect(within(chainA).getByText("11")).toBeInTheDocument();
  });

  it("clicking a residue cell toggles that key in the store", () => {
    render(<SequencePanel />);
    fireEvent.click(screen.getByRole("button", { name: "Residue A:3" }));
    expect(useStore.getState().selected.has("A:3")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Residue A:3" }));
    expect(useStore.getState().selected.has("A:3")).toBe(false);
  });

  it("renders a selected residue in its selected state", () => {
    render(<SequencePanel />);
    const cell = screen.getByRole("button", { name: "Residue B:2" });
    expect(cell).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(cell);

    const selectedCell = screen.getByRole("button", { name: "Residue B:2" });
    expect(selectedCell).toHaveAttribute("aria-pressed", "true");
    expect(selectedCell.className).toContain("bg-zinc-100");
  });

  it("scrolls a key that arrives from outside (e.g. a 3D click) into view", () => {
    render(<SequencePanel />);
    scrollIntoView.mockClear();

    // Simulate the Mol* -> store direction.
    act(() => {
      useStore.getState().toggleResidue("A:9");
    });

    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
    expect(
      screen.getByRole("button", { name: "Residue A:9" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("resolves a valid A:123 search into a single selection", () => {
    render(<SequencePanel />);
    fireEvent.change(screen.getByLabelText("Find residue"), {
      target: { value: "b:3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Go" }));

    expect([...useStore.getState().selected]).toEqual(["B:3"]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an inline error for an out-of-range search and selects nothing", () => {
    render(<SequencePanel />);
    fireEvent.change(screen.getByLabelText("Find residue"), {
      target: { value: "A:999" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Go" }));

    expect(screen.getByRole("alert").textContent).toBe(
      "No residue A:999 — chain A has 12 residues",
    );
    expect(useStore.getState().selected.size).toBe(0);
  });

  it("renders a muted placeholder when there is no protein", () => {
    resetStore(null);
    render(<SequencePanel />);
    expect(screen.getByText(/No sequence available/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Find residue")).toBeNull();
  });

  it("renders a muted placeholder when the protein has no chains", () => {
    resetStore({ ...SUMMARY, chains: [] });
    render(<SequencePanel />);
    expect(screen.getByText(/No sequence available/i)).toBeInTheDocument();
  });
});
