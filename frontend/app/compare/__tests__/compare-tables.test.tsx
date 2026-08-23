import { describe, it, expect } from "vitest";
import { render, screen, within, cleanup, fireEvent } from "@testing-library/react";
import { afterEach } from "vitest";
import { CompositionTable } from "../compare-composition";
import {
  ChainLengthTable,
  MetricsTable,
  SecondaryStructureTable,
} from "../compare-metrics";
import { sharedColoringOptions } from "../compare-viewers";
import type {
  ChainLengthPair,
  CompositionDelta,
  MetricDelta,
  SecondaryStructureDelta,
} from "@/lib/types";

afterEach(cleanup);

const MINUS = "−";

function ss(overrides: Partial<SecondaryStructureDelta> = {}): SecondaryStructureDelta {
  return {
    helix_a: 0.4567,
    helix_b: 0.0,
    helix_delta: -0.4567,
    sheet_a: 0.1739,
    sheet_b: 0.0,
    sheet_delta: -0.1739,
    coil_a: 0.3696,
    coil_b: 1.0,
    coil_delta: 0.6304,
    available_a: true,
    available_b: true,
    ...overrides,
  };
}

describe("MetricsTable", () => {
  const metrics: MetricDelta[] = [
    { key: "chain_count", label: "Chains", unit: null, a: 1, b: 4, delta: 3 },
    {
      key: "molecular_weight",
      label: "Molecular weight",
      unit: "Da",
      a: 4736.43,
      b: 5807.6,
      delta: 1071.17,
    },
    { key: "atom_count", label: "Atoms", unit: null, a: 327, b: 327, delta: 0 },
  ];

  it("shows both sides and a signed delta for each metric", () => {
    render(<MetricsTable metrics={metrics} />);
    const chains = screen.getByRole("row", { name: /Chains/ });
    expect(within(chains).getByText("1")).toBeInTheDocument();
    expect(within(chains).getByText("4")).toBeInTheDocument();
    expect(within(chains).getByText("+3")).toBeInTheDocument();
  });

  it("attaches the unit to every cell of a metric that has one", () => {
    render(<MetricsTable metrics={metrics} />);
    const mw = screen.getByRole("row", { name: /Molecular weight/ });
    expect(within(mw).getByText("4,736.4 Da")).toBeInTheDocument();
    expect(within(mw).getByText("5,807.6 Da")).toBeInTheDocument();
    expect(within(mw).getByText("+1,071.2 Da")).toBeInTheDocument();
  });

  it("shows an unsigned zero when the two sides match", () => {
    render(<MetricsTable metrics={metrics} />);
    const atoms = screen.getByRole("row", { name: /Atoms/ });
    expect(within(atoms).getByText("0")).toBeInTheDocument();
  });
});

describe("ChainLengthTable", () => {
  const rows: ChainLengthPair[] = [
    { rank: 0, chain_a: "A", length_a: 46, chain_b: "H", length_b: 30, delta: -16 },
    { rank: 1, chain_a: null, length_a: null, chain_b: "L", length_b: 22, delta: null },
  ];

  it("pairs chains by rank and signs the length difference", () => {
    render(<ChainLengthTable rows={rows} />);
    const first = screen.getByRole("row", { name: /A \/ H/ });
    expect(within(first).getByText("46")).toBeInTheDocument();
    expect(within(first).getByText(`${MINUS}16`)).toBeInTheDocument();
  });

  it("keeps a chain the other structure does not have, as an em-dash row", () => {
    // "B has a third chain" is one of the more interesting things a comparison
    // can say; dropping the row would hide it.
    render(<ChainLengthTable rows={rows} />);
    const unmatched = screen.getByRole("row", { name: /— \/ L/ });
    expect(within(unmatched).getByText("22")).toBeInTheDocument();
    expect(within(unmatched).getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });
});

describe("SecondaryStructureTable", () => {
  it("renders fractions as percentages and deltas as percentage points", () => {
    render(<SecondaryStructureTable ss={ss()} />);
    const helix = screen.getByRole("row", { name: /Helix/ });
    expect(within(helix).getByText("45.7%")).toBeInTheDocument();
    expect(within(helix).getByText(`${MINUS}45.7 pp`)).toBeInTheDocument();
  });

  it("stays silent when both structures declare secondary structure", () => {
    render(<SecondaryStructureTable ss={ss()} />);
    expect(screen.queryByTestId("ss-unavailable-warning")).toBeNull();
  });

  it("warns which side declared none, naming it", () => {
    // An AlphaFold model declares no secondary structure, so its all-coil split
    // is a placeholder. Without this the table reads as a 46-point helix
    // difference that is really an absence of annotation.
    render(<SecondaryStructureTable ss={ss({ available_b: false })} />);
    const warning = screen.getByTestId("ss-unavailable-warning");
    expect(warning).toHaveTextContent("Structure B declares no secondary structure");
    expect(warning).toHaveTextContent("not a measurement");
  });

  it("warns about the A side too", () => {
    render(<SecondaryStructureTable ss={ss({ available_a: false })} />);
    expect(screen.getByTestId("ss-unavailable-warning")).toHaveTextContent(
      "Structure A declares no secondary structure",
    );
  });

  it("says so plainly when neither side declares any", () => {
    render(
      <SecondaryStructureTable ss={ss({ available_a: false, available_b: false })} />,
    );
    expect(screen.getByTestId("ss-unavailable-warning")).toHaveTextContent(
      "Neither structure declares any secondary structure",
    );
  });
});

describe("CompositionTable", () => {
  function composition(): CompositionDelta[] {
    // Twenty rows, with a deliberately non-alphabetical difference ordering.
    const alphabet = "ACDEFGHIKLMNPQRSTVWY".split("");
    return alphabet.map((aa, i) => ({
      aa,
      label: `${aa}${i}`,
      count_a: i,
      count_b: i,
      percent_a: 0,
      percent_b: 0,
      // W (index 18) is the biggest difference, A (index 0) the smallest.
      delta_percent: i % 2 === 0 ? i * 0.1 : -i * 0.1,
    }));
  }

  it("shows the largest differences first, not alphabetical order", () => {
    render(<CompositionTable rows={composition()} />);
    const rows = within(screen.getByTestId("composition-rows")).getAllByRole("row");
    expect(rows).toHaveLength(8);
    // Index 19 (Y) has |Δ| 1.9, the largest; index 0 (A) has 0 and must be out.
    expect(rows[0]).toHaveTextContent("Y");
    expect(screen.getByTestId("composition-rows")).not.toHaveTextContent("A0");
  });

  it("expands to all twenty residues and back", () => {
    render(<CompositionTable rows={composition()} />);
    fireEvent.click(screen.getByRole("button", { name: /Show all 20 residues/ }));
    expect(
      within(screen.getByTestId("composition-rows")).getAllByRole("row"),
    ).toHaveLength(20);

    fireEvent.click(screen.getByRole("button", { name: /largest differences only/ }));
    expect(
      within(screen.getByTestId("composition-rows")).getAllByRole("row"),
    ).toHaveLength(8);
  });

  it("shows percentages with counts beside them", () => {
    const rows: CompositionDelta[] = [
      {
        aa: "C",
        label: "Cys",
        count_a: 6,
        count_b: 1,
        percent_a: 13.04,
        percent_b: 2.17,
        delta_percent: -10.87,
      },
    ];
    render(<CompositionTable rows={rows} />);
    const row = screen.getByRole("row", { name: /Cys/ });
    expect(within(row).getByText("13.04%")).toBeInTheDocument();
    expect(within(row).getByText("(6)")).toBeInTheDocument();
    expect(within(row).getByText(`${MINUS}10.87 pp`)).toBeInTheDocument();
  });
});

describe("sharedColoringOptions", () => {
  function values(hasA: boolean, hasB: boolean): string[] {
    return sharedColoringOptions(hasA, hasB).map(([value]) => value);
  }

  it("offers pLDDT when both structures are predictions", () => {
    expect(values(true, true)).toContain("plddt");
    expect(values(true, true)).not.toContain("bfactor");
  });

  it("offers B-factor when neither is", () => {
    expect(values(false, false)).toContain("bfactor");
    expect(values(false, false)).not.toContain("plddt");
  });

  it("offers neither when the two disagree", () => {
    // The predicted-vs-experimental pair A3 is built around. One shared select
    // cannot label the B-factor column truthfully for both sides at once.
    for (const options of [values(true, false), values(false, true)]) {
      expect(options).not.toContain("plddt");
      expect(options).not.toContain("bfactor");
      // The structure-independent schemes survive.
      expect(options).toEqual(["chain", "ss", "hydrophobicity", "residueType"]);
    }
  });
});
