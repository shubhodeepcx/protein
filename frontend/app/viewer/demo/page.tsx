"use client";

import React, { useRef, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Atom, RotateCcw, Loader2 } from "lucide-react";
import type { MolstarViewerRef } from "@/components/molstar-viewer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL } from "@/lib/api";

// Mol* must be dynamically imported (no SSR — it touches WebGL/window).
const MolstarViewer = dynamic(() => import("@/components/molstar-viewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-zinc-950">
      <Loader2 className="size-6 animate-spin text-zinc-500" />
    </div>
  ),
});

export default function DemoViewerPage() {
  const viewerRef = useRef<MolstarViewerRef>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewerReady, setViewerReady] = useState(false);

  useEffect(() => {
    if (!viewerReady) return;
    let cancelled = false;

    (async () => {
      try {
        await viewerRef.current!.loadStructure(
          `${API_BASE_URL}/api/proteins/demo/file`,
          "pdb",
        );
      } catch {
        if (!cancelled) {
          setError("Could not load demo structure. Is the backend running?");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [viewerReady]);

  return (
    <>
      {/* Mol* ships a bundled CSS — load it as a static asset so the viewer
          UI inherits its own theme without touching the global Tailwind layer. */}
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
          <span className="text-sm font-medium">
            1CRN &mdash; Crambin (demo)
          </span>
          <Badge
            variant="outline"
            className="ml-1 border-zinc-700 text-[10px] text-zinc-400 uppercase"
          >
            P1
          </Badge>

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
            >
              <RotateCcw className="size-3.5" aria-hidden />
            </Button>
          </div>
        </header>

        {/* Viewer area */}
        <div className="relative flex-1 overflow-hidden">
          {loading && (
            <div
              role="status"
              aria-live="polite"
              className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/80"
            >
              <div className="flex flex-col items-center gap-2 text-zinc-400">
                <Loader2 className="size-6 animate-spin" aria-hidden />
                <span className="text-xs">Loading 1CRN&hellip;</span>
              </div>
            </div>
          )}
          {error && (
            <div
              role="alert"
              className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/90"
            >
              <p className="max-w-xs text-center text-sm text-red-400">
                {error}
              </p>
            </div>
          )}
          <MolstarViewer
            ref={viewerRef}
            className="h-full w-full"
            onReady={() => setViewerReady(true)}
          />
        </div>
      </div>
    </>
  );
}
