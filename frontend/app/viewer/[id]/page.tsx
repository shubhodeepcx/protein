"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";
import type { MolstarViewerRef } from "@/components/molstar-viewer";
import { ViewerRail } from "@/components/viewer-rail";
import { ViewerHeader } from "@/components/viewer-header";
import {
  ViewerOverlays,
  type ViewerError,
} from "@/components/viewer-overlays";
import { API_BASE_URL } from "@/lib/api";
import { useStore } from "@/lib/store";

// Mol* must be dynamically imported (no SSR — it touches WebGL/window).
const MolstarViewer = dynamic(() => import("@/components/molstar-viewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-zinc-950">
      <Loader2 className="size-6 animate-spin text-zinc-500" />
    </div>
  ),
});

export default function DynamicViewerPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const viewerRef = useRef<MolstarViewerRef>(null);

  // Protein metadata lives in the shared Zustand store so other surfaces
  // (sequence panel, analytics) read the same `current` protein.
  const summary = useStore((s) => s.current);
  const metaLoading = useStore((s) => s.isLoading);
  const metaError = useStore((s) => s.error);
  const loadProtein = useStore((s) => s.loadProtein);
  const clearProtein = useStore((s) => s.clearProtein);
  const selected = useStore((s) => s.selected);
  const toggleResidue = useStore((s) => s.toggleResidue);
  const clearSelection = useStore((s) => s.clearSelection);
  const representation = useStore((s) => s.representation);
  const coloring = useStore((s) => s.coloring);

  // Mol*-specific load state stays local — it's not shareable across surfaces.
  const [structureLoading, setStructureLoading] = useState(false);
  const [structureError, setStructureError] = useState<string | null>(null);
  const [viewerReady, setViewerReady] = useState(false);
  // Bumped every time a structure finishes loading, so the imperative effects
  // below re-apply their state against the freshly built Mol* hierarchy.
  const [structureVersion, setStructureVersion] = useState(0);

  // Reset ALL Mol*-local state on route change: each flag outlives a
  // MolstarViewer unmount/remount on /viewer/A → /viewer/B and would otherwise
  // describe the previous protein. viewerReady would fire the load effect at
  // the old plugin; structureVersion would push state at a dead hierarchy;
  // structureError would keep the `summary && !error` gate shut so the next
  // route's viewer never mounts and onReady never fires again; and
  // structureLoading sticks on because the cancelled load skips its `finally`.
  useEffect(() => {
    setViewerReady(false);
    setStructureVersion(0);
    setStructureError(null);
    setStructureLoading(false);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    void loadProtein(id);
    return () => {
      clearProtein();
      clearSelection();
    };
    // loadProtein/clearProtein are stable Zustand actions; depending only on id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!viewerReady || !summary) return;
    let cancelled = false;
    setStructureLoading(true);
    // Clear any prior structure error so a successful retry on the same id
    // wipes the previous failure rather than stacking on top of it.
    setStructureError(null);

    (async () => {
      try {
        await viewerRef.current!.loadStructure(
          `${API_BASE_URL}${summary.file_url}`,
          summary.file_format,
        );
        if (!cancelled) setStructureVersion((v) => v + 1);
      } catch (e) {
        if (!cancelled) {
          setStructureError(
            `Could not load structure: ${
              e instanceof Error ? e.message : String(e)
            }`,
          );
        }
      } finally {
        if (!cancelled) setStructureLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [viewerReady, summary]);

  // Store -> Mol*: selection. One effect, one direction — a Mol* click routes
  // through `onResidueClick` below and never re-enters this effect's source.
  useEffect(() => {
    if (structureVersion === 0) return;
    viewerRef.current?.highlightResidues([...selected]);
  }, [structureVersion, selected]);

  // Store -> Mol*: representation + coloring.
  useEffect(() => {
    if (structureVersion === 0) return;
    viewerRef.current?.setRepresentation(representation);
  }, [structureVersion, representation]);

  useEffect(() => {
    if (structureVersion === 0) return;
    viewerRef.current?.setColoring(coloring);
  }, [structureVersion, coloring]);

  // Mol* -> store: a 3D click toggles the residue, empty space clears.
  const onResidueClick = useCallback(
    (key: string | null) => {
      if (key === null) clearSelection();
      else toggleResidue(key);
    },
    [clearSelection, toggleResidue],
  );

  const loading = metaLoading || structureLoading;
  const error: ViewerError | null = metaError
    ? {
        kind: metaError.status === 404 ? "notfound" : "other",
        message: metaError.message,
      }
    : structureError
      ? { kind: "other", message: structureError }
      : null;

  const title =
    summary?.name && summary.name.trim().length > 0
      ? summary.name
      : `Protein ${id?.slice(0, 8) ?? ""}`;

  return (
    <>
      {/* Mol* ships a bundled CSS — load it as a static asset. */}
      <link rel="stylesheet" href="/molstar.css" />

      <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
        <ViewerHeader
          title={title}
          source={summary?.source ?? null}
          onResetCamera={() => viewerRef.current?.resetCamera()}
        />

        {/* Split content: viewer left, tabbed rail right (xl+) or stacked below. */}
        <div className="grid flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[1fr_24rem]">
          <div className="relative overflow-hidden">
            <ViewerOverlays
              loading={loading}
              error={error}
              label={summary ? title : "metadata"}
            />
            {summary && !error && (
              <MolstarViewer
                ref={viewerRef}
                className="h-full w-full"
                onReady={() => setViewerReady(true)}
                onResidueClick={onResidueClick}
                chains={summary.chains}
              />
            )}
          </div>

          {/* xl+ side panel */}
          <aside className="hidden min-h-0 border-l border-zinc-800 bg-zinc-950 xl:block">
            {id && summary && <ViewerRail proteinId={id} />}
          </aside>
        </div>

        {/* Narrow viewports: stacked rail below the viewer. */}
        <div className="border-t border-zinc-800 bg-zinc-950 xl:hidden">
          {id && summary && <ViewerRail proteinId={id} />}
        </div>
      </div>
    </>
  );
}
