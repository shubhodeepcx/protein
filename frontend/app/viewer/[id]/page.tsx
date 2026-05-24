"use client";

import React, { useRef, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  Atom,
  RotateCcw,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type {
  MolstarViewerRef,
  MolstarRepresentation,
} from "@/components/molstar-viewer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

const REPR_OPTIONS: readonly MolstarRepresentation[] = [
  "cartoon",
  "surface",
  "stick",
  "ball-stick",
  "spacefill",
] as const;

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
  const [repr, setRepr] = useState<MolstarRepresentation>("cartoon");
  const [showMeta, setShowMeta] = useState(false);

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
        kind: metaError.toLowerCase().includes("not found") ? "notfound" : "other",
        message: metaError,
      }
    : structureError
      ? { kind: "other", message: structureError }
      : null;

  function handleRepr(type: MolstarRepresentation) {
    setRepr(type);
    viewerRef.current?.setRepresentation(type);
  }

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
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs"
              onClick={() => setShowMeta((v) => !v)}
              disabled={!summary}
              aria-expanded={showMeta}
              aria-label="Toggle raw metadata"
            >
              {showMeta ? (
                <ChevronDown className="size-3.5" aria-hidden />
              ) : (
                <ChevronRight className="size-3.5" aria-hidden />
              )}
              metadata
            </Button>
            {REPR_OPTIONS.map((r) => (
              <Button
                key={r}
                size="sm"
                variant={repr === r ? "secondary" : "ghost"}
                className="h-7 text-xs"
                onClick={() => handleRepr(r)}
                disabled={!summary}
              >
                {r}
              </Button>
            ))}
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

        {/* Optional metadata panel */}
        {showMeta && summary && (
          <div className="max-h-48 shrink-0 overflow-auto border-b border-zinc-800 bg-zinc-900/40 px-4 py-2 font-mono text-[11px] leading-relaxed text-zinc-400">
            <div>
              id: <span className="text-zinc-100">{summary.id}</span>
            </div>
            <div>
              chains:{" "}
              <span className="text-zinc-100">{summary.chains.length}</span>
              {summary.chains.length > 0 && (
                <>
                  {" "}
                  ({summary.chains.map((c) => c.label).join(", ")})
                </>
              )}
            </div>
            <div>
              residues:{" "}
              <span className="text-zinc-100">
                {summary.residue_count.toLocaleString()}
              </span>
            </div>
            <div>
              atoms:{" "}
              <span className="text-zinc-100">
                {summary.atom_count.toLocaleString()}
              </span>
            </div>
            <div>
              MW:{" "}
              <span className="text-zinc-100">
                {summary.molecular_weight.toFixed(0)}
              </span>{" "}
              Da
            </div>
            <div>
              format:{" "}
              <span className="text-zinc-100">{summary.file_format}</span>
            </div>
            {summary.organism && (
              <div>
                organism:{" "}
                <span className="text-zinc-100">{summary.organism}</span>
              </div>
            )}
            {summary.warnings.length > 0 && (
              <div className="mt-1 text-amber-400">
                warnings: {summary.warnings.join("; ")}
              </div>
            )}
          </div>
        )}

        {/* Viewer area */}
        <div className="relative flex-1 overflow-hidden">
          {loading && !error && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/80">
              <div className="flex flex-col items-center gap-2 text-zinc-400">
                <Loader2 className="size-6 animate-spin" aria-hidden />
                <span className="text-xs">
                  Loading {summary ? title : "metadata"}&hellip;
                </span>
              </div>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-zinc-950/90 text-center">
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
      </div>
    </>
  );
}
