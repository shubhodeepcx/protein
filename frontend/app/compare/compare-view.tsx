"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertCircle, Loader2 } from "lucide-react";
import { apiPost, ApiError } from "@/lib/api";
import type { CompareRequest, CompareResponse } from "@/lib/types";
import { AlignmentPanel, SuperpositionCard } from "./compare-alignment";
import { CompositionTable } from "./compare-composition";
import { CompareIdForm } from "./compare-id-form";
import {
  ChainLengthTable,
  MetricsTable,
  SecondaryStructureTable,
} from "./compare-metrics";
import { CompareViewers } from "./compare-viewers";

function compareErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const detail =
      typeof e.body === "object" && e.body !== null
        ? ((e.body.detail as string | undefined) ??
          (e.body.error as string | undefined) ??
          null)
        : null;
    return `Comparison failed (${e.status}): ${detail ?? e.message}`;
  }
  return `Comparison failed: ${e instanceof Error ? e.message : String(e)}`;
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

/**
 * `/compare?a={id}&b={id}` — fetches the comparison and lays out its sections.
 *
 * One request drives everything: `POST /api/compare` returns both proteins'
 * identities alongside the diff, so the viewers and the tables can never
 * disagree about which structures are being compared.
 */
export function CompareView() {
  const params = useSearchParams();
  const a = params.get("a");
  const b = params.get("b");

  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Monotonic request token, as in `search-view.tsx` and `protein-slice.ts`:
  // editing the ids re-fires the comparison, and an older response must never
  // land on top of a newer one.
  const requestSeq = useRef(0);

  const runCompare = useCallback(async (idA: string, idB: string) => {
    const myReq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    const body: CompareRequest = { a: idA, b: idB };
    try {
      const response = await apiPost<CompareResponse>("/api/compare", body);
      if (myReq !== requestSeq.current) return;
      setData(response);
    } catch (e) {
      if (myReq !== requestSeq.current) return;
      setData(null);
      setError(compareErrorMessage(e));
    } finally {
      if (myReq === requestSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!a || !b) {
      // Supersede anything in flight so a stale response cannot repaint over
      // the id form after the query string is cleared.
      requestSeq.current += 1;
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    void runCompare(a, b);
  }, [a, b, runCompare]);

  if (!a || !b) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
        <CompareIdForm initialA={a ?? ""} initialB={b ?? ""} />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-5">
      {loading && !data && (
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Comparing structures…
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-red-900/70 bg-red-950/40 px-3 py-2 text-xs text-red-300"
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{error}</span>
        </div>
      )}

      {error && (
        <div className="mt-4">
          <CompareIdForm initialA={a} initialB={b} />
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-6">
          <CompareViewers a={data.a} b={data.b} />

          <Section title="Sequence alignment">
            <AlignmentPanel
              alignment={data.alignment}
              note={data.alignment_note}
            />
          </Section>

          <Section title="Structural superposition">
            <SuperpositionCard
              superposition={data.superposition}
              note={data.superposition_note}
            />
          </Section>

          <Section title="Metrics">
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <MetricsTable metrics={data.metrics} />
              <ChainLengthTable rows={data.chain_lengths} />
            </div>
          </Section>

          <Section title="Secondary structure">
            <SecondaryStructureTable ss={data.secondary_structure} />
          </Section>

          <Section title="Composition">
            <CompositionTable rows={data.composition} />
          </Section>
        </div>
      )}
    </main>
  );
}

export default CompareView;
