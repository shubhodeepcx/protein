"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost, ApiError } from "@/lib/api";
import type { ImportRequest, ProteinSummary, SearchSource } from "@/lib/types";

/**
 * Import a public entry and open it in the viewer (P8).
 *
 * This is the "linking back into the import flow" half of the similarity
 * results: a BLAST hit or a UniRef homolog is only useful if you can look at
 * it, and the import endpoint already turns an accession into a local viewer
 * id. Extracted into a hook because two different result lists need it.
 *
 * Failure keeps the user where they are and reports on the row that failed —
 * one bad accession must not take the rest of the table with it.
 */
export function useProteinImport() {
  const router = useRouter();
  const [importingId, setImportingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open = useCallback(
    async (sourceId: string, source: SearchSource = "uniprot") => {
      setError(null);
      setImportingId(sourceId);
      const body: ImportRequest = { source, source_id: sourceId };
      try {
        const summary = await apiPost<ProteinSummary>("/api/proteins/import", body);
        router.push(`/viewer/${summary.id}`);
      } catch (e) {
        setError(importErrorMessage(sourceId, e));
        setImportingId(null);
      }
    },
    [router],
  );

  return { importingId, error, open };
}

function importErrorMessage(sourceId: string, e: unknown): string {
  if (e instanceof ApiError) {
    const detail =
      typeof e.body === "object" && e.body !== null
        ? ((e.body.detail as string | undefined) ??
          (e.body.error as string | undefined) ??
          null)
        : null;
    // 404 here is the common, explainable case: the hit is a real UniProt
    // entry but has no structure to show, which is not the same as broken.
    return `Could not open ${sourceId}: ${detail ?? e.message}`;
  }
  return `Could not open ${sourceId}: ${e instanceof Error ? e.message : String(e)}`;
}
