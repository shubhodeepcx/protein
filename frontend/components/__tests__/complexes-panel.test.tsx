import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent, within } from "@testing-library/react";

import { ComplexesPanel } from "@/components/complexes-panel";
import { useStore } from "@/lib/store";
import type {
  ComplexParticipant,
  ProteinComplex,
  ProteinComplexes,
} from "@/lib/types";

function participant(patch: Partial<ComplexParticipant> = {}): ComplexParticipant {
  return {
    identifier: "P68871",
    name: "HBB",
    description: "Hemoglobin subunit beta",
    interactor_type: "protein",
    organism: "Homo sapiens",
    stoichiometry: "2",
    stoichiometry_min: 2,
    stoichiometry_max: 2,
    url: "https://www.uniprot.org/uniprotkb/P68871/entry",
    is_query_protein: false,
    ...patch,
  };
}

function complex(patch: Partial<ProteinComplex> = {}): ProteinComplex {
  return {
    accession: "CPX-2158",
    name: "Hemoglobin HbA complex",
    organism: "Homo sapiens",
    description: "Adult hemoglobin A binds oxygen in the lungs.",
    predicted: false,
    url: "https://www.ebi.ac.uk/complexportal/complex/CPX-2158",
    participants: [
      participant(),
      participant({ identifier: "P69905", name: "HBA1", is_query_protein: true }),
      participant({
        identifier: "CHEBI:30413",
        name: "heme b",
        description: null,
        interactor_type: "small molecule",
        stoichiometry: "4",
        stoichiometry_min: 4,
        stoichiometry_max: 4,
        url: "https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:30413",
      }),
    ],
    ...patch,
  };
}

const BASE: ProteinComplexes = {
  id: "test-id",
  accession: "P69905",
  accession_resolved: true,
  resolution_note: "Resolved directly from the uniprot accession.",
  query: "P69905",
  complexes: [complex()],
  search_matches: 1,
};

function setComplexes(patch: Partial<ProteinComplexes> = {}) {
  act(() => {
    useStore.setState({
      complexes: { ...BASE, ...patch },
      complexesLoading: false,
      complexesError: null,
      // The panel fetches on mount; these tests drive the store directly.
      loadComplexes: async () => {},
    });
  });
}

describe("ComplexesPanel", () => {
  beforeEach(() => setComplexes());
  afterEach(cleanup);

  it("fetches the protein's complexes on mount", () => {
    // Without this the tab renders whatever the store happens to hold, which
    // in the real app is null until something else populates it.
    const seen: string[] = [];
    act(() => {
      useStore.setState({
        complexes: null,
        complexesLoading: false,
        complexesError: null,
        loadComplexes: async (id: string) => {
          seen.push(id);
        },
      });
    });

    render(<ComplexesPanel proteinId="abc123" />);

    expect(seen).toEqual(["abc123"]);
  });

  it("falls back to the first complex when a shorter payload arrives", () => {
    // Selecting the 2nd of 2, then loading a protein with 1, must not index
    // past the end of the list.
    setComplexes({
      complexes: [complex(), complex({ accession: "CPX-2419", name: "HbA2" })],
      search_matches: 2,
    });
    const { rerender } = render(<ComplexesPanel proteinId="test-id" />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "1" } });
    expect(screen.getByRole("link", { name: /CPX-2419/ })).toBeInTheDocument();

    setComplexes({ complexes: [complex()], search_matches: 1 });
    rerender(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByRole("link", { name: /CPX-2158/ })).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("shows the complex name, accession link and curated function", () => {
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByText("Hemoglobin HbA complex")).toBeInTheDocument();
    expect(
      screen.getByText("Adult hemoglobin A binds oxygen in the lungs."),
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /CPX-2158/ });
    expect(link).toHaveAttribute(
      "href",
      "https://www.ebi.ac.uk/complexportal/complex/CPX-2158",
    );
  });

  it("renders a participant row per member with its stoichiometry", () => {
    render(<ComplexesPanel proteinId="test-id" />);

    const rows = within(screen.getByRole("table")).getAllByRole("row");
    // header + three participants
    expect(rows).toHaveLength(4);
    expect(within(rows[1]).getByText("HBB")).toBeInTheDocument();
    expect(within(rows[1]).getByText("2")).toBeInTheDocument();
    expect(within(rows[3]).getByText("heme b")).toBeInTheDocument();
    expect(within(rows[3]).getByText("4")).toBeInTheDocument();
  });

  it("keeps non-protein participants and labels their type", () => {
    // Complex Portal curates haem, ATP and RNA as real participants; dropping
    // them would under-count the complex.
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByText("small molecule")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /CHEBI:30413/ })).toBeInTheDocument();
  });

  it("marks the row for the protein currently open", () => {
    render(<ComplexesPanel proteinId="test-id" />);

    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(within(rows[2]).getByText("This protein")).toBeInTheDocument();
    expect(within(rows[1]).queryByText("This protein")).not.toBeInTheDocument();
  });

  it("says so rather than inventing a copy number when none was curated", () => {
    setComplexes({
      complexes: [
        complex({
          participants: [
            participant({ stoichiometry: null, stoichiometry_min: null, stoichiometry_max: null }),
          ],
        }),
      ],
    });
    render(<ComplexesPanel proteinId="test-id" />);

    const row = within(screen.getByRole("table")).getAllByRole("row")[1];
    expect(within(row).getByText("n/a")).toBeInTheDocument();
    // Scoped to the row: an uncurated copy number must not become "1" (or any
    // other number) just because the table wants something in the cell.
    expect(within(row).queryByText(/^\d+(-\d+)?$/)).not.toBeInTheDocument();
  });

  it("flags a predicted complex instead of passing it off as curated", () => {
    setComplexes({
      complexes: [complex({ predicted: true, description: null })],
    });
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByText("Predicted, not curated")).toBeInTheDocument();
    // No curated function text exists for a predicted complex, so the section
    // must not render an empty heading.
    expect(screen.queryByText("Function")).not.toBeInTheDocument();
  });

  it("offers a selector only when the protein is in several complexes", () => {
    render(<ComplexesPanel proteinId="test-id" />);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();

    cleanup();
    setComplexes({
      complexes: [complex(), complex({ accession: "CPX-2419", name: "Hemoglobin HbA2 complex" })],
      search_matches: 2,
    });
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  it("switches the detail pane when another complex is selected", () => {
    setComplexes({
      complexes: [
        complex(),
        complex({
          accession: "CPX-2419",
          name: "Hemoglobin HbA2 complex",
          description: "A minor adult form.",
        }),
      ],
      search_matches: 2,
    });
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByText("Adult hemoglobin A binds oxygen in the lungs.")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "1" } });

    expect(screen.getByText("A minor adult form.")).toBeInTheDocument();
    expect(
      screen.queryByText("Adult hemoglobin A binds oxygen in the lungs."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /CPX-2419/ })).toBeInTheDocument();
  });

  it("explains an empty result rather than showing an error", () => {
    setComplexes({ complexes: [], search_matches: 0 });
    render(<ComplexesPanel proteinId="test-id" />);

    expect(
      screen.getByText("No Complex Portal complex contains this protein."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains an unresolved accession with the resolution note", () => {
    setComplexes({
      accession: null,
      accession_resolved: false,
      resolution_note: "Uploaded structures carry no database identifier to map from.",
      complexes: [],
      search_matches: 0,
    });
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByText("No complexes for this structure.")).toBeInTheDocument();
    expect(
      screen.getByText("Uploaded structures carry no database identifier to map from."),
    ).toBeInTheDocument();
  });

  it("accounts for records the participation filter dropped", () => {
    // The count must stay visible: silently showing 7 of 9 matches would hide
    // that Complex Portal's free-text search over-matched.
    setComplexes({ search_matches: 3 });
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByText(/2 further record\(s\)/)).toBeInTheDocument();
  });

  it("says nothing about dropped records when none were dropped", () => {
    render(<ComplexesPanel proteinId="test-id" />);

    expect(screen.queryByText(/further record/)).not.toBeInTheDocument();
  });

  it("shows a spinner while loading and an alert on failure", () => {
    act(() => {
      useStore.setState({
        complexes: null,
        complexesLoading: true,
        complexesError: null,
        loadComplexes: async () => {},
      });
    });
    const { rerender } = render(<ComplexesPanel proteinId="test-id" />);
    expect(screen.getByText(/Fetching complexes/)).toBeInTheDocument();

    act(() => {
      useStore.setState({
        complexes: null,
        complexesLoading: false,
        complexesError: { status: 502, message: "Could not reach the portal." },
      });
    });
    rerender(<ComplexesPanel proteinId="test-id" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach the portal.");
  });
});
