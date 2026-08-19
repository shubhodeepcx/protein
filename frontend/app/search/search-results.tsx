"use client";

import { Database, Loader2 } from "lucide-react";
import type { SearchResponse } from "@/lib/types";
import { ResultCard } from "./result-card";

/** Where the search state machine is; owned by `SearchView`. */
export type SearchStatus = "idle" | "loading" | "done" | "error";

/**
 * Everything below the form: the idle prompt, the first-load spinner, the
 * no-matches state, and the result list.
 *
 * `data` is kept across a re-search on purpose — the previous results stay on
 * screen with `aria-busy` set rather than blinking out to a spinner.
 */
export function SearchResults({
  status,
  data,
}: {
  status: SearchStatus;
  data: SearchResponse | null;
}) {
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
