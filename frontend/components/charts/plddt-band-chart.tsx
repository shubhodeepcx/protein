"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PlddtBand } from "@/lib/types";
import { PLDDT_BAND_COLORS } from "@/lib/pae-scale";

/**
 * Distribution of residues across AlphaFold's four confidence bands.
 *
 * The band edges come off the wire (`min_plddt` / `max_plddt`) rather than
 * being hard-coded here a second time — a duplicated 70 that drifts from the
 * backend's is how a legend ends up describing the wrong measurement.
 *
 * Colours are AlphaFold DB's own, so this chart, the AFDB entry page and the
 * structure colouring in the viewer all say the same thing: blue is confident,
 * orange is not.
 */
export function PlddtBandChart({ bands }: { bands: PlddtBand[] }) {
  const data = bands.map((band) => ({
    ...band,
    range:
      band.key === "very_high"
        ? `>${band.min_plddt}`
        : band.key === "very_low"
          ? `<${band.max_plddt}`
          : `${band.min_plddt}-${band.max_plddt}`,
  }));

  return (
    <div className="flex flex-col gap-1.5">
      <ResponsiveContainer width="100%" height={130}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 8, bottom: 0, left: 4 }}
        >
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="label"
            width={62}
            tick={{ fontSize: 10, fill: "#a1a1aa" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "#27272a" }}
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              fontSize: 11,
            }}
            itemStyle={{ color: "#fafafa" }}
            formatter={(value: number) => [`${value} residues`, "Count"]}
          />
          <Bar dataKey="residue_count" radius={2}>
            {data.map((band) => (
              <Cell key={band.key} fill={PLDDT_BAND_COLORS[band.key]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* The same numbers as text. The chart renders at zero height in a
          headless environment and, more importantly, colour alone must never
          be the message. */}
      <ul className="space-y-0.5 px-1 text-[11px] text-zinc-400">
        {data.map((band) => (
          <li key={band.key} className="flex items-baseline gap-1.5">
            <span
              className="mt-[3px] inline-block size-2 shrink-0 rounded-[2px]"
              style={{ background: PLDDT_BAND_COLORS[band.key] }}
              aria-hidden
            />
            <span className="text-zinc-300">{band.label}</span>
            <span className="text-zinc-500">(pLDDT {band.range})</span>
            <span className="ml-auto tabular-nums text-zinc-300">
              {band.residue_count} · {(band.fraction * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
