"use client";

import React, { useRef, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Atom, RotateCcw, Loader2, AlertCircle } from "lucide-react";
import type { MolstarViewerRef } from "@/components/molstar-viewer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AnalyticsPanel } from "@/components/analytics-panel";
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

type ViewerError = { kind: "notfound" | "other"; message: string };

export default function DynamicViewerPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const viewerRef = useRef<MolstarViewerRef>(null);

  // Protein metadata lives in the shared Zustand store so other surfaces
  // (sidebars, future selection panels) can read the same `current` protein.
  const summary = useStore((s) => s.current);
  const metaLoading = useStore((s) => s.isLoading);
  const metaError = useStore((s) => s.error);
  const loadProtein = useStore((s) => s.loadProtein);
  const clearProtein = useStore((s) => s.clearProtein);

  // Mol*-specific load state stays local — it's not shareable across surfaces.
  const [structureLoading, setStructureLoading] = useState(false);
  const [structureError, setStructureError] = useState<string | null>(null);
  const [viewerReady, setViewerReady] = useState(false);

  // Reset viewerReady whenever the route id changes. Without this the local
  // flag survives MolstarViewer unmount/remount on /viewer/A → /viewer/B, so
  // the load effect below would fire against the previous plugin instance
  // before the new one has called onReady.
  useEffect(() => {
    setViewerReady(false);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    void loadProtein(id);
    return () => {
      clearProtein();
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
  const isNotFound = error?.kind === "notfound";

  return (
    <>
      {/* Mol* ships a bundled CSS — load it as a static asset. */}
      <link rel="stylesheet" href="/molstar.css" />

      <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
        {/* Toolbar */}
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-zinc-800 px-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-100"
          >
            <Atom className="size-4" aria-hidden />
            <span className="font-semibold">ProteoLens</span>
          </Link>
          <span aria-hidden className="text-zinc-700">
            /
          </span>
          <span className="text-sm font-medium">{title}</span>
          {summary && (
            <Badge
              variant="outline"
              className="border-zinc-700 text-[10px] text-zinc-400 uppercase"
            >
              {summary.source}
            </Badge>
          )}

          <div className="ml-auto flex items-center gap-1.5">
            <Badge
              variant="outline"
              className="border-zinc-700 text-[10px] text-zinc-400 uppercase"
            >
              cartoon
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              className="h-7"
              onClick={() => viewerRef.current?.resetCamera()}
              title="Reset camera"
              aria-label="Reset camera"
              disabled={!summary}
            >
              <RotateCcw className="size-3.5" aria-hidden />
            </Button>
          </div>
        </header>

        {/* Split content: viewer left, analytics panel right (xl+) or stacked below (narrow). */}
        <div className="grid flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[1fr_24rem]">
          <div className="relative overflow-hidden">
            {loading && !error && (
              <div
                role="status"
                aria-live="polite"
                className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/80"
              >
                <div className="flex flex-col items-center gap-2 text-zinc-400">
                  <Loader2 className="size-6 animate-spin" aria-hidden />
                  <span className="text-xs">
                    Loading {summary ? title : "metadata"}&hellip;
                  </span>
                </div>
              </div>
            )}
            {error && (
              <div
                role="alert"
                className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-zinc-950/90 text-center"
              >
                <AlertCircle className="size-8 text-red-400" aria-hidden />
                <p className="max-w-md text-sm text-red-400">{error.message}</p>
                {isNotFound && (
                  <Link
                    href="/"
                    className="text-xs text-zinc-400 underline hover:text-zinc-100"
                  >
                    Upload a new protein
                  </Link>
                )}
              </div>
            )}
            {summary && !error && (
              <MolstarViewer
                ref={viewerRef}
                className="h-full w-full"
                onReady={() => setViewerReady(true)}
              />
            )}
          </div>

          {/* xl+ side panel */}
          <aside className="hidden border-l border-zinc-800 bg-zinc-950 xl:block">
            {id && summary && <AnalyticsPanel proteinId={id} />}
          </aside>
        </div>

        {/* Narrow viewports: stacked analytics panel below the viewer. */}
        <div className="border-t border-zinc-800 bg-zinc-950 xl:hidden">
          {id && summary && <AnalyticsPanel proteinId={id} />}
        </div>
      </div>
    </>
  );
}
