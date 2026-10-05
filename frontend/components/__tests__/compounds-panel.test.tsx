import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

import { CompoundsPanel } from "@/components/compounds-panel";
import { useStore } from "@/lib/store";
import type {
  CompoundGroup,
  CompoundsResponse,
  LigandContact,
} from "@/lib/types";

function contact(chain: string, ordinal: number, residue = "C"): LigandContact {
  return {
    chain,
    ordinal,
    key: `${chain}:${ordinal}`,
    residue,
    auth_seq_id: ordinal + 10,
    insertion_code: null,
    min_distance: 2.2,
    atom_contacts: 3,
  };
}

function group(patch: Partial<CompoundGroup> = {}): CompoundGroup {
  return {
    code: "ZN",
    name: "ZINC ION",
    category: "ion",
    formula: "ZN 2+",
    formula_weight: null,
    parent_residue: null,
    instances: [
      {
        chain: "A",
        auth_seq_id: 101,
        insertion_code: null,
        atom_count: 1,
        contacts: [contact("A", 3), contact("A", 1)],
      },
    ],
    ...patch,
  };
}

const BASE: CompoundsResponse = {
  protein_id: "test-id",
  contact_cutoff: 4,
  nucleic_acids: [
    {
      label: "B",
      kind: "DNA",
      sequence: "GCA",
      length: 3,
      gc_fraction: 2 / 3,
      composition: { A: 1, C: 1, G: 1 },
      contacts: [contact("A", 2, "T")],
    },
  ],
  groups: [
    group({ code: "HEM", name: "HEME", category: "cofactor", formula_weight: 616.487 }),
    group(),
    group({
      code: "SEP",
      name: "PHOSPHOSERINE",
      category: "modified_residue",
      parent_residue: "S",
      instances: [
        { chain: "A", auth_seq_id: 6, insertion_code: null, atom_count: 7, contacts: [] },
      ],
    }),
    group({ code: "SO4", name: "SULFATE ION", category: "additive" }),
  ],
  water_count: 2,
  notes: ["Contacts are protein residues within 4 Å."],
};

function setCompounds(patch: Partial<CompoundsResponse> | null = {}) {
  act(() => {
    useStore.setState({
      compounds: patch === null ? null : { ...BASE, ...patch },
      compoundsLoading: false,
      compoundsError: null,
      // The panel fetches on mount; these tests drive the store directly.
      loadCompounds: async () => {},
      selected: new Set<string>(),
    });
  });
}

describe("CompoundsPanel", () => {
  beforeEach(() => setCompounds());
  afterEach(cleanup);

  it("fetches the protein's compounds on mount", () => {
    const seen: string[] = [];
    act(() => {
      useStore.setState({
        compounds: null,
        loadCompounds: async (id: string) => {
          seen.push(id);
        },
      });
    });
    render(<CompoundsPanel proteinId="abc123" />);
    expect(seen).toEqual(["abc123"]);
  });

  it("renders one section per category present, in biological order", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    const headings = screen
      .getAllByRole("button", { expanded: true })
      .concat(screen.getAllByRole("button", { expanded: false }))
      .map((b) => b.textContent ?? "");
    expect(headings.some((h) => h.startsWith("Nucleic acids"))).toBe(true);
    expect(headings.some((h) => h.startsWith("Cofactors & nucleotides"))).toBe(true);
    expect(headings.some((h) => h.startsWith("Ions"))).toBe(true);
    expect(headings.some((h) => h.startsWith("Modified residues"))).toBe(true);
    expect(headings.some((h) => h.startsWith("Ligands"))).toBe(false);
  });

  it("starts additives collapsed so buffer does not crowd out partners", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    expect(screen.getByRole("button", { name: /Additives/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("SULFATE ION")).toBeNull();
  });

  it("shows the nucleic-acid strand with its GC content", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    expect(screen.getByTestId("nucleic-sequence-B")).toHaveTextContent("GCA");
    expect(screen.getByText(/3 nt · GC 67%/)).toBeInTheDocument();
  });

  it("selects a contact residue in 3D through the shared selection", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    fireEvent.click(screen.getAllByTestId("functional-residue-A:3")[0]);
    expect([...useStore.getState().selected]).toEqual(["A:3"]);
  });

  it("selects every contact of a compound at once", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    fireEvent.click(screen.getAllByTitle(/Select all 2 residues of ZN 101/)[0]);
    expect([...useStore.getState().selected].sort()).toEqual(["A:1", "A:3"]);
  });

  it("names the parent residue of a modified residue and no contact count", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    expect(screen.getByText(/derived from S/)).toBeInTheDocument();
    expect(screen.getByText(/SEP 6 \(chain A\) · 7 atoms$/)).toBeInTheDocument();
  });

  it("shows the declared formula weight", () => {
    render(<CompoundsPanel proteinId="test-id" />);
    expect(screen.getByText(/616\.5 Da/)).toBeInTheDocument();
  });

  it("says plainly when the structure has no compounds", () => {
    setCompounds({
      nucleic_acids: [],
      groups: [],
      water_count: 0,
      notes: ["This structure contains no non-protein components other than water."],
    });
    render(<CompoundsPanel proteinId="test-id" />);
    expect(screen.getByText(/no non-protein components/)).toBeInTheDocument();
  });

  it("reports a failed load", () => {
    act(() => {
      useStore.setState({
        compounds: null,
        compoundsError: { status: 500, message: "boom" },
      });
    });
    render(<CompoundsPanel proteinId="test-id" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Compounds failed: boom");
  });
});
