import React from "react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// Mock next/navigation so the import link can mount without a Next.js runtime.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import { BlastHitsTable } from "@/components/blast-hits-table";
import type { BlastHit, BlastResult } from "@/lib/types";

function hit(patch: Partial<BlastHit> = {}): BlastHit {
  return {
    rank: 1,
    accession: "P35858",
    entry_id: "ALS_HUMAN",
    description: "Insulin-like growth factor-binding protein complex acid labile subunit",
    database: "SP",
    organism: "Homo sapiens",
    gene: "IGFALS",
    length: 605,
    url: "https://www.uniprot.org/uniprot/P35858",
    uniprot_accession: "P35858",
    identity_percent: 100,
    expect: 0,
    score: 3142,
    bit_score: 1214.91,
    align_length: 605,
    gaps: 0,
    hsps: [],
    ...patch,
  };
}

function result(patch: Partial<BlastResult> = {}): BlastResult {
  const hits = patch.hits ?? [hit()];
  return {
    program: "blastp",
    version: "BLASTP 2.9.0+",
    databases: ["uniprotkb_swissprot"],
    query_id: "ALS_HUMAN",
    query_definition: null,
    query_length: 605,
    hit_count: hits.length,
    hits,
    started_at: null,
    finished_at: null,
    ...patch,
    ...(patch.hits ? { hits, hit_count: hits.length } : {}),
  };
}

describe("BlastHitsTable", () => {
  beforeEach(() => {
    pushMock.mockReset();
    vi.unstubAllGlobals();
  });
  afterEach(cleanup);

  it("renders the five columns the results table is specified to carry", () => {
    render(<BlastHitsTable result={result()} />);

    expect(screen.getByText("Hit")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Identity")).toBeInTheDocument();
    expect(screen.getByText("E-value")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
  });

  it("shows the hit's accession, description, identity, E-value and score", () => {
    // Every number here is deliberately distinct from every other number on
    // the row: identity 33.4, coverage 49.9, gaps 3, score 527, rank 5. A
    // shared value would let the identity cell render `gaps` or `coverage`
    // and still satisfy a whole-row assertion.
    render(
      <BlastHitsTable
        result={result({
          hits: [
            hit({
              rank: 5,
              identity_percent: 33.4,
              align_length: 302,
              gaps: 3,
              expect: 5.5e-58,
              score: 527,
            }),
          ],
        })}
      />,
    );

    const row = screen.getByTestId("blast-hit-P35858");
    expect(row).toHaveTextContent("P35858");
    expect(row).toHaveTextContent("acid labile subunit");
    expect(row).toHaveTextContent("Homo sapiens");
    expect(row).toHaveTextContent("33.4%");
    expect(row).toHaveTextContent("5.5e-58");
    expect(row).toHaveTextContent("527");
  });

  it("renders a tiny E-value in full rather than rounding it to zero", () => {
    // 5.5e-58 and 0.024 mean very different things; a fixed-decimal format
    // would collapse the first to "0.00".
    render(
      <BlastHitsTable
        result={result({ hits: [hit({ accession: "Q8R5M3", expect: 5.5e-58 })] })}
      />,
    );

    expect(screen.getByTestId("blast-hit-Q8R5M3")).toHaveTextContent("5.5e-58");
  });

  it("shows query coverage alongside identity", () => {
    render(
      <BlastHitsTable
        result={result({ hits: [hit({ align_length: 302, identity_percent: 33.4 })] })}
      />,
    );

    expect(screen.getByTestId("blast-hit-P35858")).toHaveTextContent("49.9% cov");
  });

  it("offers no Open button for a hit that cannot be imported", () => {
    // A nucleotide hit's ENA id has no importer; a button that could only ever
    // fail is worse than no button.
    render(
      <BlastHitsTable
        result={result({
          hits: [hit({ accession: "AL021546", uniprot_accession: null, url: null })],
        })}
      />,
    );

    expect(screen.queryByRole("button", { name: /Open AL021546/ })).toBeNull();
    expect(screen.getByTestId("blast-hit-AL021546")).toHaveTextContent("no structure");
  });

  it("imports a hit and opens the resulting viewer", async () => {
    let sentBody: string | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        sentBody = String(init?.body ?? "");
        return new Response(JSON.stringify({ id: "new-uid" }), { status: 200 });
      }),
    );

    render(<BlastHitsTable result={result()} />);
    fireEvent.click(screen.getByRole("button", { name: "Open P35858 in the viewer" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/viewer/new-uid"));
    expect(JSON.parse(sentBody ?? "{}")).toEqual({
      source: "uniprot",
      source_id: "P35858",
    });
  });

  it("reports an import failure without taking the table down with it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "no AlphaFold model" }), { status: 404 }),
      ),
    );

    render(<BlastHitsTable result={result()} />);
    fireEvent.click(screen.getByRole("button", { name: "Open P35858 in the viewer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("no AlphaFold model"),
    );
    expect(pushMock).not.toHaveBeenCalled();
    // The row is still there and still actionable.
    expect(screen.getByTestId("blast-hit-P35858")).toBeInTheDocument();
  });

  it("explains an empty result instead of showing a bare table", () => {
    render(<BlastHitsTable result={result({ hits: [] })} />);

    expect(screen.getByText(/No hits above the E-value threshold/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders every hit, not just the first", () => {
    render(
      <BlastHitsTable
        result={result({
          hits: [
            hit(),
            hit({ rank: 2, accession: "O02833", identity_percent: 95.2 }),
            hit({ rank: 3, accession: "P35859", identity_percent: 77.5 }),
          ],
        })}
      />,
    );

    expect(screen.getByTestId("blast-hit-P35858")).toBeInTheDocument();
    expect(screen.getByTestId("blast-hit-O02833")).toBeInTheDocument();
    expect(screen.getByTestId("blast-hit-P35859")).toBeInTheDocument();
  });
});
