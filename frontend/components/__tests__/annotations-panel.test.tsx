import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

import { AnnotationsPanel } from "@/components/annotations-panel";
import { useStore } from "@/lib/store";
import type { ProteinAnnotations } from "@/lib/types";

/** An entry with nothing in it — every section must stay unmounted. */
const BARE: ProteinAnnotations = {
  id: "test-id",
  accession: "P01308",
  accession_resolved: true,
  resolution_note: "Resolved directly from the uniprot accession.",
  entry_name: "INS_HUMAN",
  protein_name: "Insulin",
  gene_names: ["INS"],
  organism: "Homo sapiens",
  taxon_id: 9606,
  lineage: ["Eukaryota", "Metazoa"],
  function: [],
  catalytic_activity: [],
  gene_ontology: {
    biological_process: [],
    cellular_component: [],
    molecular_function: [],
  },
  keywords: [],
  subcellular_locations: [],
  subcellular_location_notes: [],
  transmembrane: [],
  diseases: [],
  ptm: [],
  ptm_features: [],
  cross_references: [],
};

function setAnnotations(patch: Partial<ProteinAnnotations> = {}) {
  act(() => {
    useStore.setState({
      annotations: { ...BARE, ...patch },
      annotationsLoading: false,
      annotationsError: null,
      // The panel fetches on mount; these tests drive the store directly.
      loadAnnotations: async () => {},
    });
  });
}

describe("AnnotationsPanel", () => {
  beforeEach(() => setAnnotations());
  afterEach(cleanup);

  it("renders names, gene and organism from the resolved entry", () => {
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByText("Names & Origin")).toBeInTheDocument();
    expect(screen.getByText("Insulin")).toBeInTheDocument();
    expect(screen.getByText("INS")).toBeInTheDocument();
    expect(screen.getByText("Homo sapiens")).toBeInTheDocument();
  });

  it("hides every section the entry has no data for", () => {
    // This is the whole point of P6: an empty section is the complaint, so a
    // heading with nothing under it must not render at all.
    render(<AnnotationsPanel proteinId="test-id" />);

    for (const heading of [
      "Function",
      "Catalytic Activity",
      "Gene Ontology",
      "Keywords",
      "Subcellular Location",
      "Transmembrane",
      "Disease",
      "PTM / Processing",
      "Cross-references",
    ]) {
      expect(screen.queryByText(heading)).not.toBeInTheDocument();
    }
  });

  it("shows a section as soon as it has data", () => {
    setAnnotations({ function: ["Insulin decreases blood glucose concentration."] });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByText("Function")).toBeInTheDocument();
    expect(
      screen.getByText("Insulin decreases blood glucose concentration."),
    ).toBeInTheDocument();
  });

  it("groups GO terms under their three aspect headings", () => {
    setAnnotations({
      gene_ontology: {
        molecular_function: [
          { id: "GO:0005179", term: "hormone activity", evidence: "IDA" },
        ],
        biological_process: [
          { id: "GO:0008286", term: "insulin receptor signaling pathway", evidence: null },
        ],
        cellular_component: [],
      },
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByText("Molecular function")).toBeInTheDocument();
    expect(screen.getByText("Biological process")).toBeInTheDocument();
    // The aspect with no terms gets no heading either.
    expect(screen.queryByText("Cellular component")).not.toBeInTheDocument();
    expect(screen.getByText("hormone activity")).toBeInTheDocument();
    expect(screen.getByText("(IDA)")).toBeInTheDocument();
  });

  it("links catalytic activity out to Rhea and ExPASy", () => {
    setAnnotations({
      catalytic_activity: [
        {
          reaction: "L-tyrosyl-[protein] + ATP = O-phospho-L-tyrosyl-[protein] + ADP",
          ec_number: "2.7.10.1",
          rhea_ids: ["RHEA:10596"],
          chebi_ids: [],
        },
      ],
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByText(/L-tyrosyl-\[protein\]/)).toBeInTheDocument();
    expect(screen.getByText("RHEA:10596").closest("a")).toHaveAttribute(
      "href",
      "https://www.rhea-db.org/rhea/10596",
    );
    expect(screen.getByText(/EC 2\.7\.10\.1/).closest("a")).toHaveAttribute(
      "href",
      "https://enzyme.expasy.org/EC/2.7.10.1",
    );
  });

  it("renders cross-references as outbound links using the backend's URL", () => {
    setAnnotations({
      cross_references: [
        {
          database: "Reactome",
          id: "R-HSA-264876",
          description: "Insulin processing",
          url: "https://reactome.org/content/detail/R-HSA-264876",
        },
      ],
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    const link = screen.getByText("R-HSA-264876").closest("a");
    expect(link).toHaveAttribute("href", "https://reactome.org/content/detail/R-HSA-264876");
    expect(link).toHaveAttribute("target", "_blank");
    // Opening a third-party page in a new tab without this leaks window.opener.
    expect(link?.getAttribute("rel")).toContain("noopener");
  });

  it("shows a cross-reference with no URL as plain text, not a dead link", () => {
    setAnnotations({
      cross_references: [
        { database: "SIGNOR", id: "P01308", description: null, url: null },
      ],
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByText("P01308").closest("a")).toBeNull();
  });

  it("renders transmembrane spans with their residue ranges", () => {
    setAnnotations({
      transmembrane: [
        { type: "Transmembrane", description: "Helical", start: 646, end: 668 },
      ],
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByText("646–668")).toBeInTheDocument();
    expect(screen.getByText(/Helical/)).toBeInTheDocument();
  });

  it("starts expanded, then collapses and re-expands on click", () => {
    // Expanded by default on purpose: a rail of collapsed headings reads as
    // empty, which is the complaint this phase answers.
    setAnnotations({
      keywords: [{ id: "KW-0372", name: "Hormone", category: "Molecular function" }],
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    const toggle = screen.getByRole("button", { name: /Keywords/ });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Hormone")).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Hormone")).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Hormone")).toBeInTheDocument();
  });

  it("explains an unresolved accession instead of showing an error", () => {
    // An upload with no UniProt counterpart is a successful, empty response.
    setAnnotations({
      accession: null,
      accession_resolved: false,
      resolution_note: "Uploaded structures carry no database identifier to map from.",
      protein_name: null,
      gene_names: [],
      organism: null,
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // A5 appends a second sentence to the same paragraph — the panel is no
    // longer a dead end when there is no accession, because the ligands and
    // the surface profile are measured from the file. The note itself still
    // has to be shown verbatim.
    expect(
      screen.getByText(/Uploaded structures carry no database identifier to map from\./),
    ).toBeInTheDocument();
    expect(screen.queryByText("Names & Origin")).not.toBeInTheDocument();
  });

  it("reports a real failure as an alert", () => {
    act(() => {
      useStore.setState({
        annotations: null,
        annotationsLoading: false,
        annotationsError: { status: 502, message: "Could not reach UniProt." },
        loadAnnotations: async () => {},
      });
    });
    render(<AnnotationsPanel proteinId="test-id" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach UniProt.");
  });
});
