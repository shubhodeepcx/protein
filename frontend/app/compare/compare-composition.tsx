"use client";

import { useMemo, useState } from "react";
import {
  deltaToneClass,
  formatNumber,
  formatPointsDelta,
} from "@/lib/compare-format";
import type { CompositionDelta } from "@/lib/types";

const HEAD_CLASS =
  "px-2 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-zinc-500";
const CELL_CLASS = "px-2 py-1.5 text-xs tabular-nums text-zinc-200";

/**
 * Amino-acid composition, both sides plus the percentage-point difference.
 *
 * The backend always returns all twenty standard residues, zeros included, so
 * the table has a fixed twenty rows. That is a lot of rows to say "these two
 * proteins have similar composition", so it defaults to the eight biggest
 * differences with the rest one click away — the ordering by |Δ| is the
 * answer to the question the table exists to ask.
 */
export function CompositionTable({ rows }: { rows: CompositionDelta[] }) {
  const [showAll, setShowAll] = useState(false);

  const ranked = useMemo(
    () =>
      [...rows].sort(
        (x, y) =>
          Math.abs(y.delta_percent) - Math.abs(x.delta_percent) ||
          x.aa.localeCompare(y.aa),
      ),
    [rows],
  );

  const visible = showAll ? ranked : ranked.slice(0, 8);
  const hiddenCount = ranked.length - visible.length;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="overflow-x-auto rounded-md border border-zinc-800 bg-zinc-900/30">
        <table className="w-full min-w-96 border-collapse">
          <caption className="px-2 pt-2 pb-1 text-left text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
            Amino-acid composition
            {showAll ? "" : " — largest differences"}
          </caption>
          <thead>
            <tr className="border-b border-zinc-800">
              <th scope="col" className={HEAD_CLASS}>
                Residue
              </th>
              <th scope="col" className={`${HEAD_CLASS} text-right`}>
                A
              </th>
              <th scope="col" className={`${HEAD_CLASS} text-right`}>
                B
              </th>
              <th scope="col" className={`${HEAD_CLASS} text-right`}>
                Δ (B − A)
              </th>
            </tr>
          </thead>
          <tbody data-testid="composition-rows">
            {visible.map((row) => (
              <tr key={row.aa} className="border-b border-zinc-800/60 last:border-0">
                <th scope="row" className={`${CELL_CLASS} font-normal text-zinc-400`}>
                  <span className="font-mono text-zinc-300">{row.aa}</span>{" "}
                  {row.label}
                </th>
                <td className={`${CELL_CLASS} text-right`}>
                  {row.percent_a.toFixed(2)}%
                  <span className="ml-1 text-[10px] text-zinc-600">
                    ({formatNumber(row.count_a)})
                  </span>
                </td>
                <td className={`${CELL_CLASS} text-right`}>
                  {row.percent_b.toFixed(2)}%
                  <span className="ml-1 text-[10px] text-zinc-600">
                    ({formatNumber(row.count_b)})
                  </span>
                </td>
                <td
                  className={`${CELL_CLASS} text-right ${deltaToneClass(row.delta_percent)}`}
                >
                  {formatPointsDelta(row.delta_percent)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(hiddenCount > 0 || showAll) && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="self-start rounded-md border border-zinc-800 px-2 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-600"
        >
          {showAll ? "Show largest differences only" : `Show all ${ranked.length} residues`}
        </button>
      )}
    </div>
  );
}
