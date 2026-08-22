"use client";

import { AlertTriangle } from "lucide-react";
import {
  deltaToneClass,
  formatDelta,
  formatFraction,
  formatFractionDelta,
  formatNumber,
} from "@/lib/compare-format";
import type {
  ChainLengthPair,
  MetricDelta,
  SecondaryStructureDelta,
} from "@/lib/types";

const HEAD_CLASS =
  "px-2 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-zinc-500";
const CELL_CLASS = "px-2 py-1.5 text-xs tabular-nums text-zinc-200";

/** One three-column table: label, A, B, delta. */
function DiffTable({
  caption,
  children,
}: {
  caption: string;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-zinc-800 bg-zinc-900/30">
      <table className="w-full min-w-96 border-collapse">
        <caption className="px-2 pt-2 pb-1 text-left text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
          {caption}
        </caption>
        <thead>
          <tr className="border-b border-zinc-800">
            <th scope="col" className={HEAD_CLASS}>
              Metric
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
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Row({
  label,
  a,
  b,
  delta,
  deltaValue,
}: {
  label: string;
  a: string;
  b: string;
  delta: string;
  deltaValue: number;
}) {
  return (
    <tr className="border-b border-zinc-800/60 last:border-0">
      <th scope="row" className={`${CELL_CLASS} font-normal text-zinc-400`}>
        {label}
      </th>
      <td className={`${CELL_CLASS} text-right`}>{a}</td>
      <td className={`${CELL_CLASS} text-right`}>{b}</td>
      <td className={`${CELL_CLASS} text-right ${deltaToneClass(deltaValue)}`}>
        {delta}
      </td>
    </tr>
  );
}

/** Structure metrics: chains, residues, atoms, molecular weight. */
export function MetricsTable({ metrics }: { metrics: MetricDelta[] }) {
  return (
    <DiffTable caption="Structure metrics">
      {metrics.map((metric) => {
        // Molecular weight is the only fractional metric; counts stay integers.
        const digits = metric.key === "molecular_weight" ? 1 : 0;
        const unit = metric.unit ? ` ${metric.unit}` : "";
        return (
          <Row
            key={metric.key}
            label={metric.label}
            a={`${formatNumber(metric.a, digits)}${unit}`}
            b={`${formatNumber(metric.b, digits)}${unit}`}
            delta={`${formatDelta(metric.delta, digits)}${unit}`}
            deltaValue={metric.delta}
          />
        );
      })}
    </DiffTable>
  );
}

/**
 * Per-chain lengths, paired longest-first by the backend.
 *
 * A row with only one side is a chain the other structure does not have; it
 * shows an em dash rather than being dropped, because "B has a fourth chain" is
 * one of the more interesting things a comparison can say.
 */
export function ChainLengthTable({ rows }: { rows: ChainLengthPair[] }) {
  return (
    <DiffTable caption="Chain lengths (paired longest first)">
      {rows.map((row) => (
        <Row
          key={row.rank}
          label={`${row.chain_a ?? "—"} / ${row.chain_b ?? "—"}`}
          a={row.length_a === null ? "—" : formatNumber(row.length_a)}
          b={row.length_b === null ? "—" : formatNumber(row.length_b)}
          delta={row.delta === null ? "—" : formatDelta(row.delta)}
          deltaValue={row.delta ?? 0}
        />
      ))}
    </DiffTable>
  );
}

/**
 * Secondary-structure split.
 *
 * When either side reports `available: false` its file declared no secondary
 * structure at all — an AlphaFold model is the usual case — and the all-coil
 * split it shows is a placeholder. Saying so is the whole point of the flag:
 * without it the table reads as a 46-point helix difference that is really an
 * absence of annotation.
 */
export function SecondaryStructureTable({
  ss,
}: {
  ss: SecondaryStructureDelta;
}) {
  const unavailable: string[] = [];
  if (!ss.available_a) unavailable.push("A");
  if (!ss.available_b) unavailable.push("B");

  return (
    <div className="flex flex-col gap-1.5">
      <DiffTable caption="Secondary structure">
        <Row
          label="Helix"
          a={formatFraction(ss.helix_a)}
          b={formatFraction(ss.helix_b)}
          delta={formatFractionDelta(ss.helix_delta)}
          deltaValue={ss.helix_delta}
        />
        <Row
          label="Sheet"
          a={formatFraction(ss.sheet_a)}
          b={formatFraction(ss.sheet_b)}
          delta={formatFractionDelta(ss.sheet_delta)}
          deltaValue={ss.sheet_delta}
        />
        <Row
          label="Coil"
          a={formatFraction(ss.coil_a)}
          b={formatFraction(ss.coil_b)}
          delta={formatFractionDelta(ss.coil_delta)}
          deltaValue={ss.coil_delta}
        />
      </DiffTable>

      {unavailable.length > 0 && (
        <p
          data-testid="ss-unavailable-warning"
          role="status"
          className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-400"
        >
          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>
            {unavailable.length === 2
              ? "Neither structure declares any secondary structure"
              : `Structure ${unavailable[0]} declares no secondary structure`}
            , so the split above is an all-coil placeholder and these deltas are
            not a measurement.
          </span>
        </p>
      )}
    </div>
  );
}
