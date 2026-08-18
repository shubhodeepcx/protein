"use client";

import Link from "next/link";
import { Atom, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ViewerControls } from "@/components/viewer-controls";
import { useStore } from "@/lib/store";

interface ViewerHeaderProps {
  title: string;
  /** Null until protein metadata has loaded; disables the tools. */
  source: string | null;
  onResetCamera: () => void;
}

/** Workspace toolbar: breadcrumb, live selection count, and viewer controls. */
export function ViewerHeader({
  title,
  source,
  onResetCamera,
}: ViewerHeaderProps) {
  const selectedCount = useStore((s) => s.selected.size);
  const ready = source !== null;

  return (
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
      {source && (
        <Badge
          variant="outline"
          className="border-zinc-700 text-[10px] text-zinc-400 uppercase"
        >
          {source}
        </Badge>
      )}

      <div className="ml-auto flex items-center gap-1.5">
        <span
          data-testid="selection-count"
          className="text-[11px] text-zinc-500 tabular-nums"
        >
          {selectedCount} selected
        </span>
        <ViewerControls disabled={!ready} />
        <Button
          size="sm"
          variant="ghost"
          className="h-7"
          onClick={onResetCamera}
          title="Reset camera"
          aria-label="Reset camera"
          disabled={!ready}
        >
          <RotateCcw className="size-3.5" aria-hidden />
        </Button>
      </div>
    </header>
  );
}
