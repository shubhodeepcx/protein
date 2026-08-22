import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import type { CompareResponse } from "@/lib/types";

/**
 * The comparison page's orchestration: one request in, five sections out, and
 * the two ways a section can be legitimately absent.
 *
 * `CompareViewers` is stubbed — it mounts Mol*, which is a trusted library and
 * is never unit-tested here (its two-instance lifecycle has its own file,
 * `compare-viewers.test.tsx`). The API is mocked, per AGENTS.md: no test in
 * this repo reaches a live server.
 */

const searchParams = new URLSearchParams();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
  useRouter: () => ({ push }),
}));

const apiPost = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiPost: (...args: unknown[]) => apiPost(...args) };
});

vi.mock("../compare-viewers", () => ({
  CompareViewers: ({ a, b }: { a: { id: string }; b: { id: string } }) => (
    <div data-testid="compare-viewers">
      {a.id}|{b.id}
    </div>
  ),
}));

function response(overrides: Partial<CompareResponse> = {}): CompareResponse {
  return {
    a: {
      id: "aaa111",
      source: "rcsb",
      source_id: "1CRN",
      name: "Crambin",
      organism: "Crambe hispanica",
      file_url: "/api/proteins/aaa111/file",
      file_format: "mmcif",
      has_plddt: false,
    },
    b: {
      id: "bbb222",
      source: "alphafold",
      source_id: "P01542",
      name: "Crambin prediction",
      organism: "Crambe hispanica",
      file_url: "/api/proteins/bbb222/file",
      file_format: "pdb",
      has_plddt: true,
    },
    metrics: [
      { key: "chain_count", label: "Chains", unit: null, a: 1, b: 1, delta: 0 },
      { key: "residue_count", label: "Residues", unit: null, a: 46, b: 46, delta: 0 },
      { key: "atom_count", label: "Atoms", unit: null, a: 327, b: 350, delta: 23 },
      {
        key: "molecular_weight",
        label: "Molecular weight",
        unit: "Da",
        a: 4736.43,
        b: 4736.43,
        delta: 0,
      },
    ],
    chain_lengths: [
      { rank: 0, chain_a: "A", length_a: 46, chain_b: "A", length_b: 46, delta: 0 },
    ],
    composition: [
      {
        aa: "C",
        label: "Cys",
        count_a: 6,
        count_b: 6,
        percent_a: 13.04,
        percent_b: 13.04,
        delta_percent: 0,
      },
    ],
    secondary_structure: {
      helix_a: 0.4567,
      helix_b: 0,
      helix_delta: -0.4567,
      sheet_a: 0.1739,
      sheet_b: 0,
      sheet_delta: -0.1739,
      coil_a: 0.3696,
      coil_b: 1,
      coil_delta: 0.6304,
      available_a: true,
      available_b: false,
    },
    alignment: {
      chain_a: "A",
      chain_b: "A",
      length_a: 46,
      length_b: 46,
      alignment_length: 46,
      aligned_columns: 46,
      identities: 46,
      similarities: 46,
      gap_columns: 0,
      identity_percent: 100,
      similarity_percent: 100,
      identity_percent_aligned: 100,
      score: 262,
      aligned_a: "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN",
      aligned_b: "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN",
      match_line: "|".repeat(46),
    },
    alignment_note: "Aligned chain A (46 residues) against chain A (46 residues).",
    superposition: {
      chain_a: "A",
      chain_b: "A",
      rmsd: 0.42,
      atom_pairs: 46,
      residue_pairs: 46,
      identity_percent: 100,
      caveat: null,
    },
    superposition_note: "Fitted 46 alpha-carbon pairs.",
    ...overrides,
  };
}

async function renderView() {
  const { CompareView } = await import("../compare-view");
  return render(<CompareView />);
}

beforeEach(() => {
  searchParams.forEach((_, key) => searchParams.delete(key));
  for (const key of [...searchParams.keys()]) searchParams.delete(key);
  apiPost.mockReset();
  push.mockReset();
});

afterEach(cleanup);

describe("CompareView", () => {
  it("asks for two ids when the query string carries neither", async () => {
    await renderView();
    expect(screen.getByRole("heading", { name: /Choose two structures/ })).toBeInTheDocument();
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("still asks when only one id is given, keeping the one it has", async () => {
    searchParams.set("a", "aaa111");
    await renderView();
    expect(screen.getByLabelText("Protein A id")).toHaveValue("aaa111");
    expect(screen.getByLabelText("Protein B id")).toHaveValue("");
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("posts both ids and renders every section", async () => {
    searchParams.set("a", "aaa111");
    searchParams.set("b", "bbb222");
    apiPost.mockResolvedValue(response());
    await renderView();

    await waitFor(() => expect(screen.getByTestId("compare-viewers")).toBeInTheDocument());
    expect(apiPost).toHaveBeenCalledWith("/api/compare", { a: "aaa111", b: "bbb222" });

    // Both structures reach the viewers, and each table is populated.
    expect(screen.getByTestId("compare-viewers")).toHaveTextContent("aaa111|bbb222");
    expect(screen.getByRole("row", { name: /Atoms/ })).toHaveTextContent("+23");
    expect(screen.getByText("0.42 Å")).toBeInTheDocument();
    expect(screen.getByTestId("alignment-blocks")).toHaveTextContent("TTCCPSIVAR");
    expect(screen.getByRole("row", { name: /Cys/ })).toBeInTheDocument();
    // The AlphaFold side declares no secondary structure — that must be said.
    expect(screen.getByTestId("ss-unavailable-warning")).toHaveTextContent("Structure B");
  });

  it("shows the alignment note instead of an alignment when there is none", async () => {
    searchParams.set("a", "aaa111");
    searchParams.set("b", "bbb222");
    apiPost.mockResolvedValue(
      response({
        alignment: null,
        alignment_note: "No sequence alignment: protein B has no chain Z.",
        superposition: null,
        superposition_note: "No superposition: it needs a sequence alignment first.",
      }),
    );
    await renderView();

    await waitFor(() => expect(screen.getByTestId("alignment-note")).toBeInTheDocument());
    expect(screen.getByTestId("alignment-note")).toHaveTextContent("has no chain Z");
    expect(screen.getByTestId("superposition-note")).toHaveTextContent(
      "needs a sequence alignment first",
    );
    expect(screen.queryByTestId("alignment-blocks")).toBeNull();
    // Layer 1 survives layer 2's absence: the metric diff is still shown.
    expect(screen.getByRole("row", { name: /Atoms/ })).toBeInTheDocument();
  });

  it("shows an RMSD caveat as prominently as the number it qualifies", async () => {
    searchParams.set("a", "aaa111");
    searchParams.set("b", "bbb222");
    apiPost.mockResolvedValue(
      response({
        superposition: {
          chain_a: "A",
          chain_b: "A",
          rmsd: 12.5,
          atom_pairs: 5,
          residue_pairs: 5,
          identity_percent: 9,
          caveat: "Sequence identity is only 9%, inside the twilight zone.",
        },
      }),
    );
    await renderView();

    await waitFor(() => expect(screen.getByText("12.50 Å")).toBeInTheDocument());
    expect(screen.getByTestId("superposition-caveat")).toHaveTextContent("twilight zone");
  });

  it("surfaces a failed comparison and offers the ids back for editing", async () => {
    searchParams.set("a", "aaa111");
    searchParams.set("b", "bbb222");
    const { ApiError } = await import("@/lib/api");
    apiPost.mockRejectedValue(new ApiError(404, "Protein B not found", { detail: "Protein B not found" }));
    await renderView();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("Comparison failed (404): Protein B not found");
    // The user can fix the bad id without going back to the URL bar.
    expect(screen.getByLabelText("Protein B id")).toHaveValue("bbb222");
  });
});
