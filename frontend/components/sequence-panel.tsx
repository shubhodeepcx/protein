"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { SequenceChain } from "@/components/sequence-chain";
import {
  parseResidueQuery,
  RESIDUE_CLASS_LABEL,
  RESIDUE_CLASS_ORDER,
  RESIDUE_CLASS_SWATCH,
} from "@/lib/residue";

// Re-exported so the `A:123` parser is reachable from the panel's own module.
export { parseResidueQuery } from "@/lib/residue";

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 px-3 pb-2 text-[10px] text-zinc-500">
      {RESIDUE_CLASS_ORDER.map((cls) => (
        <span key={cls} className="flex items-center gap-1">
          <span
            aria-hidden
            className={`inline-block size-2 rounded-[2px] ${RESIDUE_CLASS_SWATCH[cls]}`}
          />
          {RESIDUE_CLASS_LABEL[cls]}
        </span>
      ))}
    </div>
  );
}

/**
 * Sequence rail: per-chain residue grids wired to `selectionSlice`.
 *
 * Two-way sync with the 3D viewer runs through the store — clicking a cell
 * calls `toggleResidue`, and any key that arrives in `selected` (including one
 * pushed by a Mol* click) is scrolled into view here.
 */
export function SequencePanel() {
  const chains = useStore((s) => s.current)?.chains;
  const selected = useStore((s) => s.selected);
  const toggleResidue = useStore((s) => s.toggleResidue);
  const setSelection = useStore((s) => s.setSelection);
  const clearSelection = useStore((s) => s.clearSelection);

  const [query, setQuery] = useState("");
  const [queryError, setQueryError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const previousRef = useRef<ReadonlySet<string>>(new Set());
  const pendingScrollRef = useRef<string | null>(null);

  // Scroll-to-selected. Runs once per `selected` change (one direction only),
  // so a 3D click that lands in the store never bounces back out of here.
  useEffect(() => {
    const previous = previousRef.current;
    previousRef.current = selected;

    const added = [...selected].filter((key) => !previous.has(key));
    const target = pendingScrollRef.current ?? added[added.length - 1];
    pendingScrollRef.current = null;
    if (!target) return;

    const cell = containerRef.current?.querySelector(
      `[data-residue-key="${target}"]`,
    );
    cell?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  const onSubmit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault();
      const result = parseResidueQuery(query, chains ?? []);
      if (!result.ok) {
        setQueryError(result.error);
        return;
      }
      setQueryError(null);
      pendingScrollRef.current = result.key;
      setSelection([result.key]);
    },
    [query, chains, setSelection],
  );

  if (!chains || chains.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">
          No sequence available — load a protein with at least one chain.
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex h-full flex-col overflow-y-auto">
      <form onSubmit={onSubmit} className="flex items-center gap-2 p-3 pb-2">
        <div className="relative flex-1">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-zinc-500"
          />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setQueryError(null);
            }}
            placeholder="Find residue, e.g. A:12"
            aria-label="Find residue"
            className="h-7 w-full rounded-md border border-zinc-800 bg-zinc-900/30 pl-7 pr-2 font-mono text-xs text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="h-7 shrink-0 rounded-md border border-zinc-800 bg-zinc-900/30 px-2 text-[11px] text-zinc-300 hover:bg-zinc-800"
        >
          Go
        </button>
      </form>

      {queryError && (
        <p role="alert" className="px-3 pb-2 text-[11px] text-red-400">
          {queryError}
        </p>
      )}

      <Legend />

      <div className="flex items-center justify-between px-3 pb-2 text-[10px] text-zinc-500">
        <span>
          {selected.size} residue{selected.size === 1 ? "" : "s"} selected
        </span>
        {selected.size > 0 && (
          <button
            type="button"
            onClick={() => clearSelection()}
            className="flex items-center gap-1 text-zinc-400 hover:text-zinc-100"
          >
            <X aria-hidden className="size-3" />
            Clear
          </button>
        )}
      </div>

      {chains.map((chain) => (
        <SequenceChain
          key={chain.id}
          chain={chain}
          selected={selected}
          onToggle={toggleResidue}
        />
      ))}
    </div>
  );
}
