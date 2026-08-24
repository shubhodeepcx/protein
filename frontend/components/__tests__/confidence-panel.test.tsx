/**
 * A1 — the confidence panel, its band chart, its region warnings and the PAE
 * heatmap.
 *
 * The claims under test are the ones that would otherwise ship as a confident
 * wrong picture:
 *
 * * an experimental structure must say "not applicable", never render an empty
 *   or zeroed heatmap (P10's donut and P7's comparison warning set this
 *   precedent after a placeholder shipped as a measurement);
 * * a binned matrix must say it is binned, in the UI, in words;
 * * the low-confidence message must be readable as text — colour alone is not
 *   the message;
 * * "very low" (< 50, likely disordered) must stay a distinct claim from
 *   "low" (50-70, merely uncertain).
 */

import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, within } from "@testing-library/react";

import { ConfidencePanel } from "@/components/confidence-panel";
import { useStore } from "@/lib/store";
import type {
  ConfidenceResponse,
  LowConfidenceRegion,
  PaeMatrix,
  PlddtBand,
} from "@/lib/types";

function bands(counts: [number, number, number, number]): PlddtBand[] {
  const total = counts.reduce((a, b) => a + b, 0) || 1;
  const rows: Array<[PlddtBand["key"], string, number, number]> = [
    ["very_high", "Very high", 90, 100],
    ["confident", "Confident", 70, 90],
    ["low", "Low", 50, 70],
    ["very_low", "Very low", 0, 50],
  ];
  return rows.map(([key, label, min, max], i) => ({
    key,
    label,
    min_plddt: min,
    max_plddt: max,
    residue_count: counts[i],
    fraction: counts[i] / total,
    description: `${label} band.`,
  }));
}

function region(patch: Partial<LowConfidenceRegion> = {}): LowConfidenceRegion {
  return {
    chain_id: "A",
    start: 16,
    end: 110,
    length: 95,
    mean_plddt: 48.6,
    min_plddt: 37.66,
    band: "very_low",
    likely_disordered: true,
    label:
      "Chain A residues 16-110 (95 residues, mean pLDDT 48.6, lowest 37.7) — likely disordered, do not interpret as a fold",
    ...patch,
  };
}

/** A small square matrix whose diagonal is zero, as real PAE always is. */
function matrix(size: number): number[][] {
  return Array.from({ length: size }, (_, i) =>
    Array.from({ length: size }, (_, j) => Math.abs(i - j) * 2),
  );
}

function pae(patch: Partial<PaeMatrix> = {}): PaeMatrix {
  return {
    available: true,
    unavailable_reason: "",
    residue_count: 8,
    size: 8,
    bin_size: 1,
    downsampled: false,
    max_cells: 16384,
    aggregation: "none",
    max_error: 31.75,
    resolution_label:
      "Full resolution — one cell per residue pair (8 x 8 cells, 8 residues).",
    values: matrix(8),
    source_url: "https://alphafold.ebi.ac.uk/files/x.json",
    ...patch,
  };
}

const BASE: ConfidenceResponse = {
  id: "test-id",
  has_plddt: true,
  note: "",
  accession: "P01308",
  residue_count: 110,
  mean_plddt: 52.91,
  bands: bands([0, 14, 40, 56]),
  low_confidence_regions: [
    region({
      start: 1,
      end: 1,
      length: 1,
      mean_plddt: 64.44,
      min_plddt: 64.44,
      band: "low",
      likely_disordered: false,
      label:
        "Chain A residue 1 (1 residue, mean pLDDT 64.4, lowest 64.4) — treat the fold here with caution",
    }),
    region(),
  ],
  low_confidence_residue_count: 96,
  low_confidence_fraction: 96 / 110,
  low_confidence_threshold: 70,
  pae: pae(),
  warnings: [],
};

function setConfidence(patch: Partial<ConfidenceResponse> = {}) {
  act(() => {
    useStore.setState({
      confidence: { ...BASE, ...patch },
      confidenceLoading: false,
      confidenceError: null,
      loadConfidence: async () => {},
    });
  });
}

describe("ConfidencePanel", () => {
  beforeEach(() => setConfidence());
  afterEach(cleanup);

  it("fetches confidence on mount", () => {
    const seen: string[] = [];
    act(() => {
      useStore.setState({
        confidence: null,
        confidenceLoading: false,
        confidenceError: null,
        loadConfidence: async (id: string) => {
          seen.push(id);
        },
      });
    });

    render(<ConfidencePanel proteinId="abc123" />);
    expect(seen).toEqual(["abc123"]);
  });

  it("shows the mean pLDDT and the accession it used", () => {
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByTestId("mean-plddt")).toHaveTextContent("52.9");
    expect(screen.getByText(/AlphaFold P01308/)).toBeInTheDocument();
  });

  it("lists every band as text, with its pLDDT range and count", () => {
    render(<ConfidencePanel proteinId="test-id" />);
    // Colour is not the message: the counts must be legible without it.
    expect(screen.getByText("(pLDDT >90)")).toBeInTheDocument();
    expect(screen.getByText("(pLDDT 70-90)")).toBeInTheDocument();
    expect(screen.getByText("(pLDDT 50-70)")).toBeInTheDocument();
    expect(screen.getByText("(pLDDT <50)")).toBeInTheDocument();
    expect(screen.getByText("56 · 50.9%")).toBeInTheDocument();
  });

  it("keeps an empty band visible rather than dropping its row", () => {
    render(<ConfidencePanel proteinId="test-id" />);
    // Very high is 0 here. A missing row would read as "the band does not
    // exist" rather than "no residue reached it".
    expect(screen.getByText("Very high")).toBeInTheDocument();
    expect(screen.getByText("0 · 0.0%")).toBeInTheDocument();
  });

  it("takes the band ranges from the wire, not from a hard-coded 70", () => {
    setConfidence({ bands: bands([1, 1, 1, 1]).map((b) =>
      b.key === "low" ? { ...b, min_plddt: 55, max_plddt: 75 } : b,
    ) });
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByText("(pLDDT 55-75)")).toBeInTheDocument();
  });
});

describe("low-confidence warnings", () => {
  beforeEach(() => setConfidence());
  afterEach(cleanup);

  it("states the total as residues and percent, not just a colour", () => {
    render(<ConfidencePanel proteinId="test-id" />);
    const summary = screen.getByTestId("low-confidence-summary");
    expect(summary).toHaveTextContent("96 of 110 residues");
    expect(summary).toHaveTextContent("87%");
    expect(summary).toHaveTextContent("below pLDDT 70");
    expect(summary).toHaveTextContent("2 regions");
  });

  it("separates 'likely disordered' from merely 'low'", () => {
    render(<ConfidencePanel proteinId="test-id" />);
    const summary = screen.getByTestId("low-confidence-summary");
    // One of the two regions dips below 50; the other does not.
    expect(summary).toHaveTextContent("1 of them dips below 50");

    const items = within(screen.getByTestId("low-confidence-list")).getAllByRole(
      "listitem",
    );
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("low");
    expect(items[0]).not.toHaveTextContent("disordered");
    expect(items[1]).toHaveTextContent("very low");
    expect(items[1]).toHaveTextContent("likely disordered");
  });

  it("prints the residue range of every region", () => {
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByText(/Chain A residue 1 /)).toBeInTheDocument();
    expect(screen.getByText(/Chain A residues 16-110/)).toBeInTheDocument();
  });

  it("does not truncate a long region list", () => {
    const many = Array.from({ length: 40 }, (_, i) =>
      region({
        start: i * 4 + 1,
        end: i * 4 + 2,
        length: 2,
        label: `Chain A residues ${i * 4 + 1}-${i * 4 + 2} (2 residues, mean pLDDT 40.0, lowest 40.0) — likely disordered, do not interpret as a fold`,
      }),
    );
    setConfidence({ low_confidence_regions: many, low_confidence_residue_count: 80 });
    render(<ConfidencePanel proteinId="test-id" />);
    expect(
      within(screen.getByTestId("low-confidence-list")).getAllByRole("listitem"),
    ).toHaveLength(40);
  });

  it("says so plainly when nothing is low confidence", () => {
    setConfidence({
      low_confidence_regions: [],
      low_confidence_residue_count: 0,
      low_confidence_fraction: 0,
      bands: bands([100, 10, 0, 0]),
    });
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByTestId("no-low-confidence")).toHaveTextContent(
      /No residue .* below pLDDT 70/,
    );
    expect(screen.queryByTestId("low-confidence-list")).not.toBeInTheDocument();
  });
});

describe("PAE heatmap", () => {
  afterEach(cleanup);

  it("renders a canvas sized to the matrix, not one node per cell", () => {
    setConfidence();
    render(<ConfidencePanel proteinId="test-id" />);
    const canvas = screen.getByTestId("pae-canvas") as HTMLCanvasElement;
    expect(canvas.width).toBe(8);
    expect(canvas.height).toBe(8);
  });

  it("states the resolution verbatim from the API", () => {
    setConfidence();
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByTestId("pae-resolution")).toHaveTextContent(
      "Full resolution",
    );
  });

  it("says a binned matrix is binned, and by how much", () => {
    // An undeclared downsample is a quiet lie about the data. The label has to
    // reach the screen, not just the payload.
    setConfidence({
      pae: pae({
        residue_count: 1273,
        size: 128,
        bin_size: 10,
        downsampled: true,
        aggregation: "mean",
        resolution_label:
          "Binned 10x — each cell is the mean predicted aligned error over a 10 x 10 block of residue pairs (1273 residues shown as 128 x 128 cells).",
        values: matrix(8),
      }),
    });
    render(<ConfidencePanel proteinId="test-id" />);
    const label = screen.getByTestId("pae-resolution");
    expect(label).toHaveTextContent("Binned 10x");
    expect(label).toHaveTextContent("1273 residues");
    expect(label).toHaveTextContent("128 x 128");
    expect(label).toHaveTextContent("mean");
  });

  it("names the direction of the scale in words", () => {
    setConfidence();
    render(<ConfidencePanel proteinId="test-id" />);
    // "Lower is better" must be stated: PAE and pLDDT run opposite ways and a
    // reader arriving from the pLDDT colouring will assume the wrong one.
    expect(screen.getByText("Lower is better")).toBeInTheDocument();
    expect(screen.getByText(/0 Å — confidently placed/)).toBeInTheDocument();
    expect(screen.getByText(/31\.8 Å — uncertain/)).toBeInTheDocument();
  });

  it("carries the figures as text, so colour is never the only message", () => {
    setConfidence();
    render(<ConfidencePanel proteinId="test-id" />);
    // matrix(8) is |i-j|*2: median 4 A, worst 14 A, 34 of 64 cells under 5 A.
    expect(screen.getByText("4.0 Å")).toBeInTheDocument();
    expect(screen.getByText("14.0 Å")).toBeInTheDocument();
    expect(screen.getByText("53%")).toBeInTheDocument();
    expect(screen.getByText(/of residue pairs are within 5/)).toBeInTheDocument();
  });

  it("renders the reason, not an empty grid, when there is no PAE", () => {
    setConfidence({
      pae: pae({
        available: false,
        unavailable_reason:
          "Predicted aligned error is published per AlphaFold DB entry, and this structure has no AlphaFold accession.",
        values: [],
        size: 0,
        residue_count: 0,
      }),
    });
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByTestId("pae-unavailable")).toHaveTextContent(
      "no AlphaFold accession",
    );
    expect(screen.queryByTestId("pae-canvas")).not.toBeInTheDocument();
  });

  it("falls back to a message rather than a blank square when canvas is absent", () => {
    // jsdom has no 2d context. A blank canvas would read as "0 A everywhere",
    // i.e. a perfect prediction, so the component has to say the image is
    // missing.
    setConfidence();
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByTestId("pae-canvas-unpainted")).toHaveTextContent(
      /could not be drawn/,
    );
  });
});

describe("structures with no pLDDT", () => {
  afterEach(cleanup);

  it("says not applicable instead of drawing an empty analysis", () => {
    setConfidence({
      has_plddt: false,
      note: "This is an experimental structure, so it carries no pLDDT confidence scores and no predicted aligned error.",
      accession: null,
      residue_count: 0,
      mean_plddt: null,
      bands: [],
      low_confidence_regions: [],
      low_confidence_residue_count: 0,
      low_confidence_fraction: 0,
      pae: pae({ available: false, values: [], size: 0, residue_count: 0 }),
    });
    render(<ConfidencePanel proteinId="test-id" />);

    expect(screen.getByTestId("confidence-not-applicable")).toHaveTextContent(
      "experimental structure",
    );
    // Nothing else may render: no zeroed band table, no empty heatmap, no
    // "0 low-confidence regions" that reads as a clean bill of health.
    expect(screen.queryByTestId("pae-canvas")).not.toBeInTheDocument();
    expect(screen.queryByTestId("no-low-confidence")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mean-plddt")).not.toBeInTheDocument();
    expect(screen.queryByText("Very high")).not.toBeInTheDocument();
  });

  it("surfaces a residue-count mismatch warning", () => {
    setConfidence({
      warnings: ["Chain A: scored 99 residues but the sequence has 110. Residue ranges below may be offset."],
    });
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByRole("alert")).toHaveTextContent("may be offset");
  });

  it("reports a transport failure as an error, not as an absence", () => {
    act(() => {
      useStore.setState({
        confidence: null,
        confidenceLoading: false,
        confidenceError: { status: 500, message: "boom" },
        loadConfidence: async () => {},
      });
    });
    render(<ConfidencePanel proteinId="test-id" />);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    expect(screen.queryByTestId("confidence-not-applicable")).not.toBeInTheDocument();
  });
});
