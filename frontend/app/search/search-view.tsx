"use client";

import { useCallback, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { apiGet, ApiError } from "@/lib/api";
import type { SearchResponse, SearchSourceFilter } from "@/lib/types";
import { SearchForm } from "./search-form";
import { SearchResults, type SearchStatus } from "./search-results";
import { sourceLabel } from "./source-badge";

function searchErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const detail =
      typeof e.body === "object" && e.body !== null
        ? ((e.body.detail as string | undefined) ??
          (e.body.error as string | undefined) ??
          null)
        : null;
    return `Search failed (${e.status}): ${detail ?? e.message}`;
  }
  return `Search failed: ${e instanceof Error ? e.message : String(e)}`;
}

/**
 * The search page's state machine and request sequencing.
 *
 * Presentation lives in three siblings — `SearchForm`, `SearchResults`, and
 * `ResultCard` — mirroring how P4 decomposed the viewer page. This file owns
 * only what has to be owned in one place: the query, the filter, and the
 * in-flight token below.
 */
export function SearchView() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<SearchSourceFilter>("all");
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Monotonic request token, mirroring `lib/store/protein-slice.ts`: every
  // search takes the next number and any response whose number is no longer
  // the latest is discarded. Without it, switching the source filter mid-flight
  // lets the older all-sources response land last and repaint the list with
  // results the filter says are excluded. A ref (not a module-level counter)
  // keeps the sequence per-mount.
  const searchSeq = useRef(0);

  const runSearch = useCallback(async (q: string, src: SearchSourceFilter) => {
    // Take the token BEFORE validating. An invalid submit still supersedes
    // whatever is in flight — otherwise clearing the box and switching the
    // filter mid-search lets the old response land on top of the validation
    // error and repaint results the user can no longer see a query for.
    const myReq = ++searchSeq.current;
    const trimmed = q.trim();
    if (!trimmed) {
      setError("Enter a protein name, PDB ID, or UniProt accession to search.");
      setStatus("error");
      return;
    }
    setStatus("loading");
    setError(null);
    const params = new URLSearchParams({ q: trimmed, source: src });
    try {
      const response = await apiGet<SearchResponse>(`/api/search?${params.toString()}`);
      if (myReq !== searchSeq.current) return; // a newer search started; drop this
      setData(response);
      setStatus("done");
    } catch (e) {
      if (myReq !== searchSeq.current) return;
      setData(null);
      setError(searchErrorMessage(e));
      setStatus("error");
    }
  }, []);

  // Changing the source re-runs the last query so the filter narrows what is
  // already on screen instead of needing a second submit.
  const handleSourceChange = useCallback(
    (next: SearchSourceFilter) => {
      setSource(next);
      if (status !== "idle") void runSearch(query, next);
    },
    [query, runSearch, status],
  );

  return (
    <div className="flex flex-col gap-4">
      <SearchForm
        query={query}
        source={source}
        isLoading={status === "loading"}
        onQueryChange={setQuery}
        onSourceChange={handleSourceChange}
        onSubmit={() => void runSearch(query, source)}
      />

      {status === "error" && error && (
        <div
          role="alert"
          className="rounded-md border border-red-900/70 bg-red-950/40 px-3 py-2 text-xs text-red-300"
        >
          {error}
        </div>
      )}

      {data && data.failed_sources.length > 0 && (
        <div
          data-testid="failed-sources-banner"
          role="status"
          className="flex items-start gap-2 rounded-md border border-amber-900/70 bg-amber-950/30 px-3 py-2 text-xs text-amber-300"
        >
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            Showing partial results: no response from{" "}
            {data.failed_sources.map(sourceLabel).join(", ")}.
          </span>
        </div>
      )}

      <SearchResults status={status} data={data} />
    </div>
  );
}

export default SearchView;
