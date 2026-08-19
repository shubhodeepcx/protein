"use client";

import { Loader2, Search } from "lucide-react";
import type { SearchSourceFilter } from "@/lib/types";

const SOURCE_OPTIONS: { value: SearchSourceFilter; label: string }[] = [
  { value: "all", label: "All sources" },
  { value: "rcsb", label: "RCSB PDB" },
  { value: "alphafold", label: "AlphaFold DB" },
  { value: "uniprot", label: "UniProt" },
];

export interface SearchFormProps {
  query: string;
  source: SearchSourceFilter;
  isLoading: boolean;
  onQueryChange: (query: string) => void;
  /** Changing the source re-runs the last query — see `SearchView`. */
  onSourceChange: (source: SearchSourceFilter) => void;
  onSubmit: () => void;
}

/**
 * The query input, source filter, and submit button.
 *
 * Fully controlled: every piece of state lives in `SearchView`, which owns the
 * request sequencing. This component only renders and reports.
 */
export function SearchForm({
  query,
  source,
  isLoading,
  onQueryChange,
  onSourceChange,
  onSubmit,
}: SearchFormProps) {
  return (
    <form
      data-testid="search-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
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
          onChange={(e) => onQueryChange(e.target.value)}
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
        onChange={(e) => onSourceChange(e.target.value as SearchSourceFilter)}
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
  );
}
