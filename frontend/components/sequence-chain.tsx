"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { ChainInfo } from "@/lib/types";
import { residueClass, residueKey, RESIDUE_CLASS_TEXT } from "@/lib/residue";

/** Residues per row. The gutter then doubles as a ruler every 10 residues. */
const COLS = 10;

interface SequenceChainProps {
  chain: ChainInfo;
  selected: ReadonlySet<string>;
  onToggle: (key: string) => void;
}

/**
 * One chain block: header, then the one-letter sequence as a clickable
 * monospace grid. Positions are 1-based within the chain — see `lib/residue.ts`
 * for why that, and not `auth_seq_id`, is the canonical numbering.
 */
export function SequenceChain({ chain, selected, onToggle }: SequenceChainProps) {
  const residues = Array.from(chain.sequence);
  const rowCount = Math.ceil(residues.length / COLS);

  return (
    <div className="border-t border-zinc-800 px-3 py-3">
      <h3 className="mb-2 flex items-baseline gap-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        <span>Chain {chain.label}</span>
        <span className="font-normal normal-case tracking-normal text-zinc-500">
          {chain.residue_count.toLocaleString()} residues
        </span>
      </h3>

      <div
        className="grid gap-x-0.5 gap-y-0.5"
        style={{ gridTemplateColumns: `2.75rem repeat(${COLS}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: rowCount }, (_, row) => {
          const start = row * COLS;
          return (
            <React.Fragment key={row}>
              <span
                aria-hidden
                className="pr-1 text-right font-mono text-[10px] leading-5 text-zinc-600 tabular-nums"
              >
                {start + 1}
              </span>
              {residues.slice(start, start + COLS).map((aa, offset) => {
                const position = start + offset + 1;
                const key = residueKey(chain.label, position);
                const isSelected = selected.has(key);
                return (
                  <button
                    key={key}
                    type="button"
                    data-residue-key={key}
                    aria-pressed={isSelected}
                    aria-label={`Residue ${key}`}
                    title={`${aa} ${key}`}
                    onClick={() => onToggle(key)}
                    className={cn(
                      "h-5 rounded-[3px] text-center font-mono text-[11px] leading-5 transition-colors",
                      "focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-zinc-300",
                      isSelected
                        ? "bg-zinc-100 font-semibold text-zinc-950 ring-1 ring-zinc-100"
                        : cn(RESIDUE_CLASS_TEXT[residueClass(aa)], "hover:bg-zinc-800"),
                    )}
                  >
                    {aa}
                  </button>
                );
              })}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
