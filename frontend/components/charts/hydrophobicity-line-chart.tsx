"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type { HydrophobicityProfile } from "@/lib/types";

export function HydrophobicityLineChart({ data }: { data: HydrophobicityProfile }) {
  // Map window-center positions to (window/2)-offset residue indices for x-axis labels.
  const half = Math.floor(data.window / 2);
  const series = data.values.map((v, i) => ({ pos: i + half + 1, value: v }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={series} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="#27272a" />
        <XAxis dataKey="pos" stroke="#a1a1aa" tick={{ fontSize: 10 }} />
        <YAxis
          stroke="#a1a1aa"
          tick={{ fontSize: 10 }}
          width={28}
          domain={[-4.5, 4.5]}
        />
        <ReferenceLine y={0} stroke="#52525b" strokeDasharray="2 2" />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }}
          itemStyle={{ color: "#fafafa" }}
          labelStyle={{ color: "#a1a1aa" }}
          labelFormatter={(v) => `residue ${v}`}
          formatter={(value: number) => [
            value.toFixed(2),
            `KD (chain ${data.chain_id}, w=${data.window})`,
          ]}
        />
        <Line type="monotone" dataKey="value" stroke="#10b981" strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
