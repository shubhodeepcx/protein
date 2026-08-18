import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
  within,
} from "@testing-library/react";
import type { SearchResponse, SearchResult } from "@/lib/types";

// Mock next/navigation so the page can mount without a Next.js runtime.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import { SearchView } from "@/app/search/search-view";

function hit(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    source: "rcsb",
    source_id: "1CRN",
    title: "Crambin",
    organism: "Crambe hispanica subsp. abyssinica",
    description: "A small hydrophobic plant seed protein.",
    resolution: 1.5,
    method: "X-ray",
    release_year: 1981,
    sequence_length: 46,
    confidence: null,
    ...overrides,
  };
}

function searchResponse(overrides: Partial<SearchResponse> = {}): SearchResponse {
  return { query: "crambin", results: [hit()], failed_sources: [], ...overrides };
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

/** The URL string passed to the most recent fetch call. */
function lastFetchUrl(fetchMock: ReturnType<typeof vi.fn>): string {
  return String(fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0]);
}

function submitSearch(term: string): void {
  fireEvent.change(screen.getByLabelText(/search public protein databases/i), {
    target: { value: term },
  });
  fireEvent.submit(screen.getByTestId("search-form"));
}

describe("SearchView", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    cleanup();
    pushMock.mockReset();
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the not-yet-searched state and never calls the API on mount", () => {
    render(<SearchView />);
    expect(screen.getByTestId("empty-state").textContent).toMatch(
      /Search RCSB PDB, AlphaFold DB, and UniProt/i,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders a result card with title, badge, id, organism, and description", async () => {
    fetchMock.mockResolvedValue(jsonResponse(searchResponse()));
    render(<SearchView />);

    submitSearch("crambin");

    const card = await screen.findByTestId("result-card-rcsb-1CRN");
    expect(within(card).getByTestId("source-badge-rcsb")).toBeInTheDocument();
    expect(card.textContent).toContain("1CRN");
    expect(card.textContent).toContain("Crambin");
    expect(card.textContent).toContain("Crambe hispanica");
    expect(card.textContent).toContain("hydrophobic plant seed protein");
    expect(lastFetchUrl(fetchMock)).toContain("q=crambin");
    expect(lastFetchUrl(fetchMock)).toContain("source=all");
  });

  it("narrows the query when the source filter changes", async () => {
    fetchMock.mockResolvedValue(jsonResponse(searchResponse()));
    render(<SearchView />);

    submitSearch("crambin");
    await screen.findByTestId("result-card-rcsb-1CRN");
    expect(lastFetchUrl(fetchMock)).toContain("source=all");

    fireEvent.change(screen.getByLabelText(/source database/i), {
      target: { value: "rcsb" },
    });

    await waitFor(() => expect(lastFetchUrl(fetchMock)).toContain("source=rcsb"));
    expect(lastFetchUrl(fetchMock)).toContain("q=crambin");
  });

  it("discards a stale search response that lands after a newer one", async () => {
    // Deferred all-sources request; the RCSB request that supersedes it resolves first.
    let releaseAll: (r: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        releaseAll = resolve;
      }),
    );
    render(<SearchView />);
    submitSearch("insulin");
    expect(lastFetchUrl(fetchMock)).toContain("source=all");

    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        searchResponse({
          query: "insulin",
          results: [hit({ source: "rcsb", source_id: "1BOM", title: "Insulin hexamer" })],
        }),
      ),
    );
    fireEvent.change(screen.getByLabelText(/source database/i), {
      target: { value: "rcsb" },
    });

    // The newer, narrower response lands first and paints.
    await screen.findByTestId("result-card-rcsb-1BOM");

    // Now the superseded all-sources response finally arrives.
    releaseAll(
      jsonResponse(
        searchResponse({
          query: "insulin",
          results: [
            hit({ source: "uniprot", source_id: "P01308", title: "Insulin" }),
            hit({ source: "alphafold", source_id: "P06213", title: "Insulin receptor" }),
          ],
        }),
      ),
    );

    // It must be dropped: the filter reads RCSB, so the list must stay RCSB-only.
    await waitFor(() =>
      expect(screen.getByTestId("result-list").children).toHaveLength(1),
    );
    expect(screen.getByTestId("result-card-rcsb-1BOM")).toBeInTheDocument();
    expect(screen.queryByTestId("result-card-uniprot-P01308")).not.toBeInTheDocument();
    expect(screen.queryByTestId("result-card-alphafold-P06213")).not.toBeInTheDocument();
  });

  it("lets an invalid submit supersede a search still in flight", async () => {
    // Clearing the box and switching the filter mid-search must not leave the
    // old response free to land on top of the validation error.
    let releaseAll: (r: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        releaseAll = resolve;
      }),
    );
    render(<SearchView />);
    submitSearch("insulin");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Empty the input, then change the source — runSearch bails on validation.
    fireEvent.change(screen.getByLabelText(/search public protein databases/i), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText(/source database/i), {
      target: { value: "rcsb" },
    });

    expect(screen.getByRole("alert").textContent).toMatch(/Enter a protein name/i);
    expect(fetchMock).toHaveBeenCalledTimes(1); // the invalid submit issued nothing

    // The superseded in-flight response finally arrives.
    releaseAll(jsonResponse(searchResponse()));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    // It must be discarded: the validation error stands, no results painted.
    expect(screen.getByRole("alert").textContent).toMatch(/Enter a protein name/i);
    expect(screen.queryByTestId("result-list")).not.toBeInTheDocument();
    expect(screen.queryByTestId("result-card-rcsb-1CRN")).not.toBeInTheDocument();
  });

  it("shows a distinct empty-results state", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(searchResponse({ query: "zzzz", results: [] })),
    );
    render(<SearchView />);

    submitSearch("zzzz");

    const empty = await screen.findByTestId("empty-state");
    expect(empty.textContent).toMatch(/No matches for/i);
  });

  it("banners failed sources without hiding the results that worked", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        searchResponse({
          results: [hit({ source: "uniprot", source_id: "P01308", title: "Insulin" })],
          failed_sources: ["rcsb", "alphafold"],
        }),
      ),
    );
    render(<SearchView />);

    submitSearch("insulin");

    const banner = await screen.findByTestId("failed-sources-banner");
    expect(banner.textContent).toContain("RCSB PDB");
    expect(banner.textContent).toContain("AlphaFold");
    expect(screen.getByTestId("result-card-uniprot-P01308")).toBeInTheDocument();
  });

  it("rejects a blank query client-side without calling the API", () => {
    render(<SearchView />);
    fireEvent.submit(screen.getByTestId("search-form"));
    expect(screen.getByRole("alert").textContent).toMatch(/Enter a protein name/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a search failure inline", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "boom" }, 500));
    render(<SearchView />);

    submitSearch("insulin");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Search failed \(500\)/);
    expect(alert.textContent).toMatch(/boom/);
  });
});

describe("SearchView import", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    cleanup();
    pushMock.mockReset();
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function renderWithOneResult(): Promise<HTMLElement> {
    fetchMock.mockResolvedValueOnce(jsonResponse(searchResponse()));
    render(<SearchView />);
    submitSearch("crambin");
    return screen.findByTestId("result-card-rcsb-1CRN");
  }

  it("posts the import and routes to the viewer on success", async () => {
    const card = await renderWithOneResult();
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "abc123", source: "rcsb" }));

    fireEvent.click(within(card).getByRole("button", { name: /import 1CRN/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/viewer/abc123"));

    const importCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(String(importCall[0])).toContain("/api/proteins/import");
    const init = importCall[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      source: "rcsb",
      source_id: "1CRN",
    });
  });

  it("shows a spinner on the importing card while the request is in flight", async () => {
    const card = await renderWithOneResult();
    let release: (r: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        release = resolve;
      }),
    );

    fireEvent.click(within(card).getByRole("button", { name: /import 1CRN/i }));

    await waitFor(() => expect(card.dataset.importing).toBe("true"));
    expect(within(card).getByTestId("import-spinner")).toBeInTheDocument();

    release(jsonResponse({ id: "abc123" }));
    await waitFor(() => expect(pushMock).toHaveBeenCalled());
  });

  it("shows an inline error on the card when the import fails and does not route", async () => {
    const card = await renderWithOneResult();
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "RCSB PDB has no entry '1CRN'." }, 404),
    );

    fireEvent.click(within(card).getByRole("button", { name: /import 1CRN/i }));

    const alert = await within(card).findByRole("alert");
    expect(alert.textContent).toMatch(/Import failed \(404\)/);
    expect(alert.textContent).toMatch(/no entry/);
    expect(pushMock).not.toHaveBeenCalled();
    // The card is interactive again so the user can retry.
    expect(card.dataset.importing).toBe("false");
  });
});
