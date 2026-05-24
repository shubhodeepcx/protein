"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { ChainLength } from "@/lib/types";

export function ChainLengthBarChart({ data }: { data: ChainLength[] }) {
  return (
    <ResponsiveContainer width="100%" height={150}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="#27272a" vertical={false} />
        <XAxis dataKey="chain_id" stroke="#a1a1aa" tick={{ fontSize: 10 }} />
        <YAxis stroke="#a1a1aa" tick={{ fontSize: 10 }} width={28} />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }}
          itemStyle={{ color: "#fafafa" }}
          labelStyle={{ color: "#a1a1aa" }}
          formatter={(v: number) => [`${v} residues`, "length"]}
          labelFormatter={(v) => `chain ${v}`}
        />
        <Bar dataKey="length" fill="#a855f7" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
