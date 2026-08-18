"use client";

import Link from "next/link";
import { Loader2, AlertCircle } from "lucide-react";

export type ViewerError = { kind: "notfound" | "other"; message: string };

interface ViewerOverlaysProps {
  loading: boolean;
  error: ViewerError | null;
  /** What we are waiting on — shown in the loading label. */
  label: string;
}

/** Loading / error overlays stacked above the Mol* canvas. */
export function ViewerOverlays({ loading, error, label }: ViewerOverlaysProps) {
  if (error) {
    return (
      <div
        role="alert"
        className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-zinc-950/90 text-center"
      >
        <AlertCircle className="size-8 text-red-400" aria-hidden />
        <p className="max-w-md text-sm text-red-400">{error.message}</p>
        {error.kind === "notfound" && (
          <Link
            href="/"
            className="text-xs text-zinc-400 underline hover:text-zinc-100"
          >
            Upload a new protein
          </Link>
        )}
      </div>
    );
  }

  if (!loading) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/80"
    >
      <div className="flex flex-col items-center gap-2 text-zinc-400">
        <Loader2 className="size-6 animate-spin" aria-hidden />
        <span className="text-xs">Loading {label}&hellip;</span>
      </div>
    </div>
  );
}
