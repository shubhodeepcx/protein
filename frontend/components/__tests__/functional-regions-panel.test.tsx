import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent, within } from "@testing-library/react";

import { FunctionalRegionsPanel } from "@/components/functional-regions-panel";
import { useStore } from "@/lib/store";
import type { FunctionalRegions, ResidueRef } from "@/lib/types";

/**
 * A5 — the panel's job is to keep two kinds of claim apart and to select
 * through the machinery that already exists.
 *
 * The payload below is the real shape of `GET /functional-regions` for 1HEW:
 * UniProt P00698 numbers an 18-residue signal peptide the crystal does not
 * contain, so the curated active site at UniProt 53 is Glu35 in the file. The
 * chip must therefore read `A:35`, never `A:53` — displaying the UniProt
 * position as if it were a residue number is the exact bug this feature is
 * built to avoid, and it would be invisible to anyone but a lysozyme expert.
 */

function ref(chain: string, ordinal: number, residue: string, auth: number): ResidueRef {
  return {
    chain,
    ordinal,
    key: `${chain}:${ordinal}`,
    residue,
    auth_seq_id: auth,
    insertion_code: null,
  };
}

const LYSOZYME: FunctionalRegions = {
  id: "test-id",
  accession: "P00698",
  accession_resolved: true,
  resolution_note: "Mapped from PDB 1HEW via its polymer entity.",
  chain_mappings: [
    {
      chain: "A",
      mapped: true,
      residue_count: 129,
      aligned_columns: 129,
      identity_percent: 100,
      coverage_percent: 100,
      uniprot_start: 19,
      uniprot_end: 147,
      offset_note:
        "UniProt 19-147 covers chain A residues 1-129 (numbered 1-129 in the file).",
      note: "",
    },
  ],
  active_sites: [
    {
      kind: "active_site",
      provenance: "uniprot",
      label: "Active site",
      description: null,
      ligand: null,
      ligand_id: null,
      ligand_part: null,
      evidence_codes: ["ECO:0000255"],
      experimental: false,
      uniprot_start: 53,
      uniprot_end: 53,
      uniprot_residues: "E",
      positions: [ref("A", 35, "E", 35)],
      located: true,
      location_note: "",
      substitutions: [],
    },
  ],
  binding_sites: [
    {
      kind: "binding_site",
      provenance: "uniprot",
      label: "Binding site (substrate)",
      description: null,
      ligand: "substrate",
      ligand_id: null,
      ligand_part: null,
      evidence_codes: ["ECO:0000269"],
      experimental: true,
      uniprot_start: 119,
      uniprot_end: 119,
      uniprot_residues: "D",
      positions: [ref("A", 101, "D", 101)],
      located: true,
      location_note: "",
      substitutions: [],
    },
  ],
  other_sites: [],
  dna_binding: [],
  ligands: [
    {
      component: "NAG",
      provenance: "structure",
      chain: "B",
      auth_seq_id: 2,
      insertion_code: null,
      label: "NAG 2 (chain B)",
      atom_count: 14,
      single_atom: false,
      contacts: [
        { ...ref("A", 101, "D", 101), min_distance: 2.4, atom_contacts: 3 },
        { ...ref("A", 63, "W", 63), min_distance: 3.53, atom_contacts: 1 },
      ],
    },
  ],
  contact_cutoff: 4.0,
  surface: [
    {
      chain: "A",
      sequence: "K".repeat(129),
      hydropathy: Array(129).fill(-3.9),
      charge: Array(129).fill(1),
      relative_accessibility: Array(129).fill(0.5),
      surface_exposed: Array(129).fill(true),
      net_charge: 8,
      histidine_count: 1,
      mean_hydropathy: -0.4721,
      surface_mean_hydropathy: -1.9662,
      surface_net_charge: 7,
    },
  ],
  surface_note: "Solvent accessibility is Shrake-Rupley area over the polymer alone.",
  priority_residues: [
    {
      ...ref("A", 101, "D", 101),
      reasons: ["Curated: Binding site (substrate)", "Contacts NAG 2 (chain B) at 2.40 A"],
      provenance: ["uniprot", "structure"],
      evidence_kinds: 2,
      curated_active_site: false,
      curated_binding_site: true,
      ligand_contact: true,
      hydropathy: -3.5,
      charge: -1,
      relative_accessibility: 0.571,
    },
    {
      ...ref("A", 35, "E", 35),
      reasons: ["Curated: Active site"],
      provenance: ["uniprot"],
      evidence_kinds: 1,
      curated_active_site: true,
      curated_binding_site: false,
      ligand_contact: false,
      hydropathy: -3.5,
      charge: -1,
      relative_accessibility: 0.144,
    },
  ],
  unlocated_sites: 0,
  notes: [
    "Pockets shown here are observed: they are the residues in contact with a ligand present in this coordinate file. ProteoLens does not predict pockets in a structure that has no bound ligand.",
  ],
};

function setFunctional(patch: Partial<FunctionalRegions> = {}) {
  act(() => {
    useStore.setState({
      functional: { ...LYSOZYME, ...patch },
      functionalLoading: false,
      functionalError: null,
      loadFunctional: async () => {},
      selected: new Set<string>(),
    });
  });
}

/**
 * Queries scoped to one collapsible section.
 *
 * A residue legitimately appears in several sections at once — that is the
 * whole point of the priority list — so an unscoped `getByTestId` finds more
 * than one chip and proves nothing about where it is.
 */
function section(title: string): HTMLElement {
  const heading = screen.getByRole("button", { name: new RegExp(title, "i") });
  const element = heading.closest("section");
  if (!element) throw new Error(`No section for ${title}`);
  return element as HTMLElement;
}

describe("FunctionalRegionsPanel", () => {
  beforeEach(() => setFunctional());
  afterEach(cleanup);

  it("labels a curated site by its structure ordinal, not its UniProt position", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);
    const sites = within(section("Active sites"));

    expect(sites.getByTestId("functional-residue-A:35")).toHaveTextContent("EA:35");
    expect(screen.queryByTestId("functional-residue-A:53")).toBeNull();
    // The UniProt position is still shown — labelled as a UniProt position.
    expect(sites.getByText("UniProt 53")).toBeInTheDocument();
  });

  it("puts the file's own residue number in the tooltip, never in the label", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(
      within(section("Active sites")).getByTestId("functional-residue-A:35"),
    ).toHaveAttribute("title", expect.stringContaining("numbered 35 in the file"));
  });

  it("keeps labelling by ordinal when the file numbers the residue differently", () => {
    // 1HEW numbers its chain 1-129 with no gaps, so ordinal and auth_seq_id
    // coincide there and a label built from the wrong one would look right.
    // 1HVR does not: its chain A has 98 modelled residues numbered 1-99, so
    // ordinal 80 is the residue the file calls 81. That is the case a chip
    // must not get wrong, because the selection key is the ordinal and a chip
    // reading `A:81` would select a residue one place further along.
    setFunctional({
      active_sites: [],
      binding_sites: [],
      priority_residues: [],
      ligands: [
        {
          ...LYSOZYME.ligands[0],
          label: "XK2 263 (chain A)",
          contacts: [
            { ...ref("B", 80, "P", 81), min_distance: 3.52, atom_contacts: 2 },
          ],
        },
      ],
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);
    const chip = within(section("Bound ligands")).getByTestId(
      "functional-residue-B:80",
    );

    expect(chip).toHaveTextContent("PB:80");
    expect(chip.textContent).not.toContain("81");
    expect(chip).toHaveAttribute(
      "title",
      expect.stringContaining("numbered 81 in the file"),
    );
    fireEvent.click(chip);
    expect(Array.from(useStore.getState().selected)).toEqual(["B:80"]);
  });

  it("selects through the existing setSelection when a residue is clicked", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    fireEvent.click(
      within(section("Active sites")).getByTestId("functional-residue-A:35"),
    );

    expect(Array.from(useStore.getState().selected)).toEqual(["A:35"]);
  });

  it("reflects a selection made anywhere else in the app", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);
    act(() => useStore.getState().setSelection(["A:101"]));

    for (const chip of screen.getAllByTestId("functional-residue-A:101")) {
      expect(chip).toHaveAttribute("aria-pressed", "true");
    }
    for (const chip of screen.getAllByTestId("functional-residue-A:35")) {
      expect(chip).toHaveAttribute("aria-pressed", "false");
    }
  });

  it("selects every contact of a ligand at once", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    fireEvent.click(screen.getByTitle("Select all 2 residues of NAG 2 (chain B)"));

    expect(Array.from(useStore.getState().selected).sort()).toEqual(["A:101", "A:63"]);
  });

  it("distinguishes experimental evidence from an inferred rule", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getByText("inferred")).toBeInTheDocument();
    expect(screen.getByText("experimental")).toBeInTheDocument();
  });

  it("says a site could not be placed rather than placing it somewhere", () => {
    setFunctional({
      active_sites: [
        {
          ...LYSOZYME.active_sites[0],
          positions: [],
          located: false,
          location_note:
            "UniProt position 53 could not be located in this structure — outside the modelled construct, or unmodelled within it.",
        },
      ],
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);
    const sites = within(section("Active sites"));

    expect(sites.queryByTestId("functional-residue-A:35")).toBeNull();
    expect(sites.getByText(/could not be located in this structure/)).toBeInTheDocument();
  });

  it("says how much of a partly-present feature is missing", () => {
    // A located site can still be incomplete: a construct that starts mid-loop
    // carries some of a nine-residue P-loop and not the rest. Rendering the
    // chips without the note would present a partial site as a whole one.
    setFunctional({
      binding_sites: [
        {
          ...LYSOZYME.binding_sites[0],
          uniprot_start: 718,
          uniprot_end: 726,
          location_note:
            "2 of 9 position(s) in this feature are not present in the structure: 718-719.",
        },
      ],
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);
    const sites = within(section("Ligand-binding sites"));

    expect(sites.getByTestId("functional-residue-A:101")).toBeInTheDocument();
    expect(
      sites.getByText(/2 of 9 position\(s\) in this feature are not present/),
    ).toBeInTheDocument();
  });

  it("shows a substitution rather than hiding it", () => {
    setFunctional({
      active_sites: [
        {
          ...LYSOZYME.active_sites[0],
          substitutions: ["A:35 is A here but E in UniProt"],
        },
      ],
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getByText("A:35 is A here but E in UniProt")).toBeInTheDocument();
  });

  it("leads the priority list with the residue two sources agree on", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(
      screen.getByText(/1 residue is both curated by UniProt and observed/),
    ).toBeInTheDocument();
    const chips = screen
      .getAllByRole("button")
      .filter((el) => el.getAttribute("data-testid")?.startsWith("functional-residue-"));
    // The panel renders sites before pockets before priority, so the ordering
    // under test is the priority list's own.
    const priority = chips.filter((el) => el.closest("li")?.textContent?.includes("Curated:"));
    expect(priority[0]).toHaveAttribute("data-testid", "functional-residue-A:101");
  });

  it("publishes the contact cutoff beside the contacts", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getByText(/within 4 Å of the ligand/)).toBeInTheDocument();
  });

  it("states that it does not predict pockets", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getByTestId("functional-notes")).toHaveTextContent(
      /does not predict pockets/,
    );
  });

  it("renders per-chain surface charge and hydrophobicity", () => {
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getByText("Surface hydrophobicity and charge")).toBeInTheDocument();
    expect(screen.getByText("+8")).toBeInTheDocument();
    expect(screen.getByText("+7")).toBeInTheDocument();
    expect(screen.getByText("-1.97")).toBeInTheDocument();
  });

  it("dashes the accessibility columns out when SASA was not computed", () => {
    setFunctional({
      surface: [
        {
          ...LYSOZYME.surface[0],
          relative_accessibility: [],
          surface_exposed: [],
          surface_mean_hydropathy: null,
          surface_net_charge: null,
        },
      ],
      surface_note: "Solvent accessibility was not computed: 40000 atoms is past the limit.",
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/past the limit/)).toBeInTheDocument();
    // The limit never truncates the halves that do not need coordinates.
    expect(screen.getByText("-0.47")).toBeInTheDocument();
  });

  it("shows how each chain was mapped, including a refusal", () => {
    setFunctional({
      chain_mappings: [
        ...LYSOZYME.chain_mappings,
        {
          chain: "B",
          mapped: false,
          residue_count: 40,
          aligned_columns: 38,
          identity_percent: 21.05,
          coverage_percent: 20,
          uniprot_start: null,
          uniprot_end: null,
          offset_note: "",
          note: "Chain B aligns to this UniProt entry at 21.05% identity over 20% of the shorter sequence.",
        },
      ],
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    fireEvent.click(screen.getByText("UniProt position mapping"));
    const mapping = within(section("UniProt position mapping"));
    expect(mapping.getByText("mapped")).toBeInTheDocument();
    expect(mapping.getByText("not mapped")).toBeInTheDocument();
    // A refused chain must show its REFUSAL, not a mapped chain's offset note.
    // Matching on the identity number alone is not enough — the stat line beside
    // the row carries the same number whichever note is rendered.
    expect(
      mapping.getByText(/Chain B aligns to this UniProt entry at 21\.05% identity/),
    ).toBeInTheDocument();
    expect(
      mapping.getByText(/UniProt 19-147 covers chain A residues 1-129/),
    ).toBeInTheDocument();
    expect(mapping.queryAllByText(/covers chain B/)).toHaveLength(0);
  });

  it("renders nothing at all before the first payload arrives", () => {
    act(() => {
      useStore.setState({
        functional: null,
        functionalLoading: false,
        functionalError: null,
        loadFunctional: async () => {},
      });
    });
    const { container } = render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(container).toBeEmptyDOMElement();
  });

  it("reports a transport failure as an alert", () => {
    act(() => {
      useStore.setState({
        functional: null,
        functionalLoading: false,
        functionalError: { status: null, message: "Network down." },
        loadFunctional: async () => {},
      });
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Network down.");
  });

  it("hides a section that has no data rather than showing an empty heading", () => {
    setFunctional({
      active_sites: [],
      binding_sites: [],
      dna_binding: [],
      other_sites: [],
      ligands: [],
      priority_residues: [],
      surface: [],
      chain_mappings: [],
    });
    render(<FunctionalRegionsPanel proteinId="test-id" />);

    for (const heading of [
      "Active sites",
      "Ligand-binding sites",
      "DNA-binding regions",
      "Other functional sites",
      "Bound ligands",
      "High-priority residues",
      "Surface hydrophobicity and charge",
      "UniProt position mapping",
    ]) {
      expect(screen.queryByText(heading)).toBeNull();
    }
    expect(screen.getByTestId("functional-notes")).toBeInTheDocument();
  });
});
