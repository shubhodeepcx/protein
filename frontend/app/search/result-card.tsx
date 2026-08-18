"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Download, Loader2 } from "lucide-react";
import { apiPost, ApiError } from "@/lib/api";
import type { ImportRequest, ProteinSummary, SearchResult } from "@/lib/types";
import { SourceBadge } from "./source-badge";

function importErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const detail =
      typeof e.body === "object" && e.body !== null
        ? ((e.body.detail as string | undefined) ??
          (e.body.error as string | undefined) ??
          null)
        : null;
    return `Import failed (${e.status}): ${detail ?? e.message}`;
  }
  return `Import failed: ${e instanceof Error ? e.message : String(e)}`;
}

/** The small grey facts under the title — only the ones this source publishes. */
function factsFor(result: SearchResult): string[] {
  const facts: string[] = [];
  if (result.method) facts.push(result.method);
  if (result.resolution !== null) facts.push(`${result.resolution.toFixed(2)} Å`);
  if (result.confidence !== null) facts.push(`pLDDT ${result.confidence.toFixed(1)}`);
  if (result.sequence_length !== null) facts.push(`${result.sequence_length} aa`);
  if (result.release_year !== null) facts.push(String(result.release_year));
  return facts;
}

export function ResultCard({ result }: { result: SearchResult }) {
  const router = useRouter();
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runImport = useCallback(async () => {
    setError(null);
    setIsImporting(true);
    const body: ImportRequest = {
      source: result.source,
      source_id: result.source_id,
    };
    try {
      const summary = await apiPost<ProteinSummary>("/api/proteins/import", body);
      router.push(`/viewer/${summary.id}`);
    } catch (e) {
      // Stay on the page and show the failure on this card only — the rest of
      // the list keeps working.
      setError(importErrorMessage(e));
      setIsImporting(false);
    }
  }, [result.source, result.source_id, router]);

  const facts = factsFor(result);

  return (
    <li
      data-testid={`result-card-${result.source}-${result.source_id}`}
      data-importing={isImporting ? "true" : "false"}
      className="rounded-md border border-zinc-800 bg-zinc-900/30 p-3"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <SourceBadge source={result.source} />
            <code className="font-mono text-xs text-zinc-300">{result.source_id}</code>
          </div>
          <h3 className="mt-1.5 truncate text-sm font-medium text-zinc-100">
            {result.title ?? "Untitled structure"}
          </h3>
          <p className="mt-0.5 text-xs italic text-zinc-400">
            {result.organism ?? "Organism unknown"}
          </p>
          {result.description && (
            <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-zinc-500">
              {result.description}
            </p>
          )}
          {facts.length > 0 && (
            <p className="mt-1.5 text-[10px] uppercase tracking-wide text-zinc-600">
              {facts.join(" · ")}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => void runImport()}
          disabled={isImporting}
          aria-busy={isImporting}
          aria-label={`Import ${result.source_id}`}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800/70 px-2.5 py-1.5 text-xs font-medium text-zinc-100 transition-colors hover:border-zinc-600 hover:bg-zinc-700/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isImporting ? (
            <Loader2 data-testid="import-spinner" className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Download className="size-3.5" aria-hidden />
          )}
          {isImporting ? "Importing…" : "Import"}
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-2 flex items-start gap-2 rounded border border-red-900/70 bg-red-950/40 px-2.5 py-1.5 text-xs text-red-300"
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{error}</span>
        </div>
      )}
    </li>
  );
}

export default ResultCard;
