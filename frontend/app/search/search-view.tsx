"use client";

import { useCallback, useRef, useState } from "react";
import { AlertTriangle, Database, Loader2, Search } from "lucide-react";
import { apiGet, ApiError } from "@/lib/api";
import type { SearchResponse, SearchSourceFilter } from "@/lib/types";
import { ResultCard } from "./result-card";
import { sourceLabel } from "./source-badge";

const SOURCE_OPTIONS: { value: SearchSourceFilter; label: string }[] = [
  { value: "all", label: "All sources" },
  { value: "rcsb", label: "RCSB PDB" },
  { value: "alphafold", label: "AlphaFold DB" },
  { value: "uniprot", label: "UniProt" },
];

type Status = "idle" | "loading" | "done" | "error";

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

export function SearchView() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<SearchSourceFilter>("all");
  const [status, setStatus] = useState<Status>("idle");
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
    const trimmed = q.trim();
    if (!trimmed) {
      setError("Enter a protein name, PDB ID, or UniProt accession to search.");
      setStatus("error");
      return;
    }
    const myReq = ++searchSeq.current;
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

  const isLoading = status === "loading";

  return (
    <div className="flex flex-col gap-4">
      <form
        data-testid="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          void runSearch(query, source);
        }}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-500"
            aria-hidden
          />
          <label htmlFor="db-search" className="sr-only">
            Search public protein databases
          </label>
          <input
            id="db-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="insulin, 1CRN, P69905…"
            className="h-9 w-full rounded-md border border-zinc-800 bg-zinc-900/50 pl-8 pr-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus-visible:border-zinc-600 focus-visible:outline-none"
          />
        </div>

        <label htmlFor="db-source" className="sr-only">
          Source database
        </label>
        <select
          id="db-source"
          value={source}
          onChange={(e) => handleSourceChange(e.target.value as SearchSourceFilter)}
          className="h-9 rounded-md border border-zinc-800 bg-zinc-900/50 px-2 text-sm text-zinc-100 focus-visible:border-zinc-600 focus-visible:outline-none"
        >
          {SOURCE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <button
          type="submit"
          disabled={isLoading}
          className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-4 text-sm font-medium text-zinc-100 transition-colors hover:bg-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
          Search
        </button>
      </form>

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
            Showing partial results — no response from{" "}
            {data.failed_sources.map(sourceLabel).join(", ")}.
          </span>
        </div>
      )}

      <ResultsRegion status={status} data={data} />
    </div>
  );
}

function ResultsRegion({ status, data }: { status: Status; data: SearchResponse | null }) {
  if (status === "idle") {
    return (
      <EmptyState
        title="Search RCSB PDB, AlphaFold DB, and UniProt"
        body="Try a protein name like “insulin”, a PDB ID like “1CRN”, or a UniProt accession like “P69905”."
      />
    );
  }

  if (status === "loading" && !data) {
    return (
      <div className="flex items-center justify-center gap-2 py-12 text-xs text-zinc-500">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Searching public databases…
      </div>
    );
  }

  if (!data) return null;

  if (data.results.length === 0) {
    return (
      <EmptyState
        title={`No matches for “${data.query}”`}
        body="Try a broader term, or switch the source filter back to All sources."
      />
    );
  }

  return (
    <section aria-busy={status === "loading"}>
      <h2 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        {data.results.length} result{data.results.length === 1 ? "" : "s"} for “{data.query}”
      </h2>
      <ul data-testid="result-list" className="flex flex-col gap-2">
        {data.results.map((r) => (
          <ResultCard key={`${r.source}:${r.source_id}`} result={r} />
        ))}
      </ul>
    </section>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center gap-2 rounded-md border border-dashed border-zinc-800 px-6 py-12 text-center"
    >
      <Database className="size-6 text-zinc-600" aria-hidden />
      <p className="text-sm font-medium text-zinc-300">{title}</p>
      <p className="max-w-md text-xs leading-relaxed text-zinc-500">{body}</p>
    </div>
  );
}

export default SearchView;
