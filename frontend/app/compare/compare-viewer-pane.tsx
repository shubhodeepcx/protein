"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AlertCircle, Loader2 } from "lucide-react";
import type { MolstarViewerRef } from "@/components/molstar-viewer";
import { API_BASE_URL } from "@/lib/api";
import type { MolstarColoring, MolstarRepresentation } from "@/lib/molstar/theming";
import type { CompareProteinRef } from "@/lib/types";

// Mol* touches WebGL and `window`, so it can never render on the server. The
// dynamic import lives at module scope, which means BOTH panes on this page
// share one lazily-loaded module — two component instances, one bundle.
const MolstarViewer = dynamic(() => import("@/components/molstar-viewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-zinc-950">
      <Loader2 className="size-5 animate-spin text-zinc-600" aria-hidden />
    </div>
  ),
});

export interface CompareViewerPaneProps {
  protein: CompareProteinRef;
  /** "A" or "B" — labels the pane and its test id. */
  side: string;
  representation: MolstarRepresentation;
  coloring: MolstarColoring;
}

/**
 * One of the two Mol* viewers on `/compare`.
 *
 * Every piece of state here is local to the instance — the ref to the viewer,
 * the ready flag, the load error, the structure version. That is the point:
 * two panes are two independent lifecycles that share nothing mutable, so
 * neither can observe or clobber the other's plugin. `MolstarViewer` itself
 * already keeps its plugin, residue index, load token, and teardown promise in
 * per-instance refs, so mounting it twice is safe by construction rather than
 * by timing — pinned in `__tests__/compare-viewers.test.tsx`.
 *
 * Deliberately NOT wired to the Zustand store: the store holds a single
 * `current` protein, and two panes have two.
 */
export function CompareViewerPane({
  protein,
  side,
  representation,
  coloring,
}: CompareViewerPaneProps) {
  const viewerRef = useRef<MolstarViewerRef>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [structureVersion, setStructureVersion] = useState(0);

  const fileUrl = `${API_BASE_URL}${protein.file_url}`;

  // Reset on protein change for the same reason the viewer page does: these
  // flags outlive a swap of the compared pair and would otherwise describe the
  // previous structure.
  useEffect(() => {
    setStructureVersion(0);
    setError(null);
    setLoading(false);
  }, [fileUrl]);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        await viewerRef.current!.loadStructure(fileUrl, protein.file_format);
        if (!cancelled) setStructureVersion((v) => v + 1);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [ready, fileUrl, protein.file_format]);

  useEffect(() => {
    if (structureVersion === 0) return;
    viewerRef.current?.setRepresentation(representation);
  }, [structureVersion, representation]);

  // `has_plddt` is an input, not a passenger: it decides whether the shared
  // `uncertainty` theme runs forwards (B-factor) or inverted (pLDDT).
  useEffect(() => {
    if (structureVersion === 0) return;
    viewerRef.current?.setColoring(coloring, { hasPlddt: protein.has_plddt });
  }, [structureVersion, coloring, protein.has_plddt]);

  const title = protein.name?.trim() || protein.source_id || protein.id.slice(0, 8);

  return (
    <section
      data-testid={`compare-pane-${side}`}
      className="flex min-h-0 min-w-0 flex-col border border-zinc-800 bg-zinc-950"
    >
      <header className="flex h-9 shrink-0 items-center gap-2 border-b border-zinc-800 px-2.5">
        <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-300">
          {side}
        </span>
        <span className="truncate text-xs font-medium text-zinc-200" title={title}>
          {title}
        </span>
        <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wide text-zinc-500">
          {protein.source}
          {protein.source_id ? ` · ${protein.source_id}` : ""}
        </span>
      </header>

      <div className="relative min-h-64 flex-1">
        {loading && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/60">
            <Loader2
              data-testid={`compare-pane-${side}-spinner`}
              className="size-5 animate-spin text-zinc-400"
              aria-hidden
            />
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="absolute inset-0 z-20 flex items-center justify-center bg-zinc-950/90 px-4"
          >
            <p className="flex items-start gap-2 text-xs text-red-300">
              <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Could not load structure: {error}
            </p>
          </div>
        )}
        <MolstarViewer
          ref={viewerRef}
          className="h-full w-full"
          onReady={() => setReady(true)}
        />
      </div>
    </section>
  );
}
