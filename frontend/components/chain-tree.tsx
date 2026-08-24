"use client";

import { useState } from "react";
import { ChevronRight, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import {
  chainKeys,
  chainSegments,
  classShares,
  segmentKeys,
  selectedInChain,
} from "@/lib/chain-stats";
import { RESIDUE_CLASS_LABEL, RESIDUE_CLASS_SWATCH } from "@/lib/residue";
import type { ChainInfo } from "@/lib/types";

/**
 * The workspace's left rail: the chain tree the landing page has promised
 * since P0 and that nothing ever built.
 *
 * It drives the *existing* selection slice — `setSelection` — and nothing
 * else. Every highlight it produces therefore travels the P4 path already in
 * place: store → `viewer/[id]/page.tsx` effect → `highlightResidues` → Mol*,
 * and store → sequence panel scroll-to-selected. There is no second selection
 * mechanism here, and a click on a chain is indistinguishable downstream from
 * the same residues being clicked one at a time.
 */
export function ChainTree() {
  const summary = useStore((s) => s.current);
  const selected = useStore((s) => s.selected);
  const setSelection = useStore((s) => s.setSelection);
  const clearSelection = useStore((s) => s.clearSelection);

  const chains = summary?.chains ?? [];
  const total = chains.reduce((sum, c) => sum + c.residue_count, 0);

  if (chains.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">
          No chains — this structure parsed without a polymer chain.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-zinc-800 px-3 py-2">
        <h2 className="text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">
          Chains &amp; residues
        </h2>
        <span className="text-[10px] text-zinc-500 tabular-nums">
          {chains.length} chain{chains.length === 1 ? "" : "s"} ·{" "}
          {total.toLocaleString()} aa
        </span>
      </div>

      <div className="flex shrink-0 items-center justify-between px-3 py-1.5 text-[10px] text-zinc-500">
        <span data-testid="chain-tree-selection-count">
          {selected.size.toLocaleString()} selected
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

      <div className="min-h-0 flex-1 overflow-y-auto">
        {chains.map((chain) => (
          <ChainRow
            key={chain.id}
            chain={chain}
            share={total === 0 ? 0 : chain.residue_count / total}
            selected={selected}
            onSelect={setSelection}
          />
        ))}
      </div>
    </div>
  );
}

interface ChainRowProps {
  chain: ChainInfo;
  /** This chain's share of the structure's residues, 0-1. */
  share: number;
  selected: ReadonlySet<string>;
  onSelect: (keys: Iterable<string>) => void;
}

function ChainRow({ chain, share, selected, onSelect }: ChainRowProps) {
  const [open, setOpen] = useState(false);
  const hits = selectedInChain(chain.label, chain.residue_count, selected);
  const shares = classShares(chain.sequence);
  const segments = chainSegments(chain.residue_count);

  return (
    <div className="border-b border-zinc-800/70">
      <div className="flex items-stretch">
        <button
          type="button"
          aria-expanded={open}
          aria-label={`${open ? "Collapse" : "Expand"} chain ${chain.label}`}
          onClick={() => setOpen((v) => !v)}
          className="flex w-7 shrink-0 items-center justify-center text-zinc-600 hover:text-zinc-300"
        >
          <ChevronRight
            aria-hidden
            className={cn("size-3.5 transition-transform", open && "rotate-90")}
          />
        </button>

        <button
          type="button"
          data-testid={`chain-select-${chain.label}`}
          onClick={() => onSelect(chainKeys(chain.label, chain.residue_count))}
          title={`Select all ${chain.residue_count} residues of chain ${chain.label}`}
          className="flex-1 py-2 pr-3 text-left hover:bg-zinc-900/60"
        >
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs font-semibold text-zinc-100">
              {chain.label}
            </span>
            <span className="text-[11px] text-zinc-400 tabular-nums">
              {chain.residue_count.toLocaleString()} aa
            </span>
            <span className="text-[10px] text-zinc-600 tabular-nums">
              {(share * 100).toFixed(0)}%
            </span>
            {hits > 0 && (
              <span className="ml-auto text-[10px] text-sky-300 tabular-nums">
                {hits.toLocaleString()} sel
              </span>
            )}
          </div>

          {/* Residue-class composition, same five classes and colours as the
              sequence panel's legend. */}
          <div
            aria-hidden
            className="mt-1.5 flex h-1 w-full overflow-hidden rounded-full bg-zinc-900"
          >
            {shares
              .filter((s) => s.count > 0)
              .map((s) => (
                <span
                  key={s.cls}
                  className={RESIDUE_CLASS_SWATCH[s.cls]}
                  style={{ width: `${s.fraction * 100}%` }}
                />
              ))}
          </div>
        </button>
      </div>

      {open && (
        <div className="px-3 pb-3">
          <ul className="mb-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-zinc-500">
            {shares
              .filter((s) => s.count > 0)
              .map((s) => (
                <li key={s.cls} className="flex items-center gap-1">
                  <span
                    aria-hidden
                    className={cn(
                      "inline-block size-2 rounded-[2px]",
                      RESIDUE_CLASS_SWATCH[s.cls],
                    )}
                  />
                  {RESIDUE_CLASS_LABEL[s.cls]}
                  <span className="tabular-nums text-zinc-400">{s.count}</span>
                </li>
              ))}
          </ul>

          <div className="flex flex-wrap gap-1">
            {segments.map((seg) => (
              <button
                key={seg.start}
                type="button"
                data-testid={`chain-segment-${chain.label}-${seg.start}`}
                onClick={() => onSelect(segmentKeys(chain.label, seg))}
                title={`Select residues ${chain.label}:${seg.start}–${chain.label}:${seg.end}`}
                className="rounded border border-zinc-800 bg-zinc-900/40 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400 tabular-nums hover:border-zinc-600 hover:text-zinc-100"
              >
                {seg.start}–{seg.end}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
