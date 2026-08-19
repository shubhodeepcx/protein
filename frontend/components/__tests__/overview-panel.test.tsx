import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";

import { OverviewPanel } from "@/components/overview-panel";
import { useStore } from "@/lib/store";
import type { ProteinSummary } from "@/lib/types";

const BASE: ProteinSummary = {
  id: "test-id",
  source: "rcsb",
  source_id: "1CRN",
  name: "Crambin",
  organism: "Crambe hispanica subsp. abyssinica",
  file_url: "/api/proteins/test-id/file",
  file_format: "mmcif",
  chains: [
    { id: "test-id:A", label: "A", sequence: "TTCC", residue_count: 4 },
  ],
  residue_count: 4,
  atom_count: 30,
  molecular_weight: 400,
  has_plddt: false,
  warnings: [],
};

function setSummary(patch: Partial<ProteinSummary> = {}) {
  act(() => {
    useStore.setState({ current: { ...BASE, ...patch } });
  });
}

describe("OverviewPanel", () => {
  beforeEach(() => setSummary());
  afterEach(cleanup);

  it("reports pLDDT when the B-factor column holds confidence scores", () => {
    setSummary({ has_plddt: true, source: "alphafold", source_id: "P69905" });
    render(<OverviewPanel />);
    expect(screen.getByText("B-factors")).toBeInTheDocument();
    expect(screen.getByText("pLDDT confidence (0–100)")).toBeInTheDocument();
  });

  it("reports temperature factors for an experimental structure", () => {
    render(<OverviewPanel />);
    expect(screen.getByText("Temperature factors")).toBeInTheDocument();
  });

  it("shows the organism an mmCIF import now carries", () => {
    // Paired with the backend fix: before it, every RCSB mmCIF import parsed to
    // organism=None and this field read "Unknown".
    render(<OverviewPanel />);
    expect(
      screen.getByText("Crambe hispanica subsp. abyssinica"),
    ).toBeInTheDocument();
  });

  it("falls back to Unknown when the parser really found no organism", () => {
    setSummary({ organism: null });
    render(<OverviewPanel />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });
});
