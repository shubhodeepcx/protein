import React from "react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, act, fireEvent, waitFor } from "@testing-library/react";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import { SimilarityPanel } from "@/components/similarity-panel";
import { useStore } from "@/lib/store";
import type { SimilarProtein, SimilarProteinsResponse } from "@/lib/types";

const PROTEIN = "abc123";

function member(patch: Partial<SimilarProtein> = {}): SimilarProtein {
  return {
    accession: "Q6YK33",
    entry_id: "INS_GORGO",
    protein_name: "Insulin",
    organism: "Gorilla gorilla gorilla (Western lowland gorilla)",
    taxon_id: 9595,
    sequence_length: 110,
    is_representative: false,
    uniprot_url: "https://www.uniprot.org/uniprotkb/Q6YK33/entry",
    ...patch,
  };
}

function similar(patch: Partial<SimilarProteinsResponse> = {}): SimilarProteinsResponse {
  return {
    id: PROTEIN,
    accession: "P01308",
    accession_resolved: true,
    resolution_note: "Resolved directly from the uniprot accession.",
    identity_threshold: 0.5,
    cluster_id: "UniRef50_P01308",
    cluster_name: "Cluster: Insulin",
    member_count: 35,
    organism_count: 20,
    members: [member()],
    truncated: true,
    ...patch,
  };
}

/** Drive the store directly; the panel's own fetch is stubbed out. */
function setSimilar(patch: Partial<SimilarProteinsResponse> = {}) {
  act(() => {
    useStore.setState({
      similar: similar(patch),
      similarLoading: false,
      similarError: null,
      loadSimilar: async () => {},
      // Keep BLAST inert — it has its own tests.
      blastJob: null,
      blastProteinId: null,
      blastSubmitting: false,
      blastError: null,
      resumeBlast: async () => {},
      submitBlast: async () => {},
      current: null,
    });
  });
}

describe("SimilarityPanel", () => {
  beforeEach(() => {
    pushMock.mockReset();
    window.localStorage.clear();
    setSimilar();
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("lists the UniRef homologs with organism and length", () => {
    render(<SimilarityPanel proteinId={PROTEIN} />);

    const row = screen.getByTestId("similar-Q6YK33");
    expect(row).toHaveTextContent("Q6YK33");
    expect(row).toHaveTextContent("Insulin");
    expect(row).toHaveTextContent("Western lowland gorilla");
    expect(row).toHaveTextContent("110 aa");
  });

  it("says how many of the cluster's members are shown", () => {
    // The list drops the query protein and any UniParc members, so "1 member"
    // next to a 35-member cluster needs explaining rather than hiding.
    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(screen.getByText(/Showing 1 of 35 cluster members/)).toBeInTheDocument();
  });

  it("spells out what the UniRef identity level means", () => {
    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(
      screen.getByText(/UniRef50, meaning members share at least 50% sequence identity/),
    ).toBeInTheDocument();
  });

  it("flags the cluster representative", () => {
    setSimilar({ members: [member({ is_representative: true })] });
    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(screen.getByTestId("similar-Q6YK33")).toHaveTextContent("rep");
  });

  it("does not flag an ordinary member as the representative", () => {
    render(<SimilarityPanel proteinId={PROTEIN} />);
    expect(screen.getByTestId("similar-Q6YK33")).not.toHaveTextContent("rep");
  });

  it("explains an unresolvable accession instead of showing an error", () => {
    // A plain upload has no UniProt counterpart. That is a normal outcome.
    setSimilar({
      accession: null,
      accession_resolved: false,
      resolution_note: "Uploaded structures carry no database identifier to map from.",
      members: [],
      cluster_id: null,
    });
    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(
      screen.getByText("Uploaded structures carry no database identifier to map from."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("never renders another protein's homologs", () => {
    // The payload names the uid it was built for, so a leftover response from
    // the previously viewed protein must not appear under this one.
    setSimilar({ id: "some-other-protein" });
    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(screen.queryByTestId("similar-Q6YK33")).toBeNull();
  });

  it("opens a homolog through the import flow", async () => {
    let sentBody: string | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        sentBody = String(init?.body ?? "");
        return new Response(JSON.stringify({ id: "new-uid" }), { status: 200 });
      }),
    );

    render(<SimilarityPanel proteinId={PROTEIN} />);
    fireEvent.click(screen.getByRole("button", { name: "Open Q6YK33 in the viewer" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/viewer/new-uid"));
    expect(JSON.parse(sentBody ?? "{}")).toEqual({
      source: "uniprot",
      source_id: "Q6YK33",
    });
  });

  it("surfaces a homolog lookup failure", () => {
    act(() => {
      useStore.setState({
        similar: null,
        similarLoading: false,
        similarError: { status: 502, message: "Could not reach UniProt" },
      });
    });
    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach UniProt");
  });

  it("offers the BLAST search without starting one on mount", () => {
    // A BLAST run costs EBI real compute. Opening a tab must not spend it.
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<SimilarityPanel proteinId={PROTEIN} />);

    expect(screen.getByRole("button", { name: /Run blastp at EBI/ })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
