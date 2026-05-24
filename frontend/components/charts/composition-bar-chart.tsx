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
import type { CompositionEntry } from "@/lib/types";

export function CompositionBarChart({ data }: { data: CompositionEntry[] }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="#27272a" vertical={false} />
        <XAxis dataKey="aa" stroke="#a1a1aa" tick={{ fontSize: 10 }} interval={0} />
        <YAxis stroke="#a1a1aa" tick={{ fontSize: 10 }} width={28} />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }}
          itemStyle={{ color: "#fafafa" }}
          labelStyle={{ color: "#a1a1aa" }}
          formatter={(value: number, _name, p) => {
            const payload = (p as { payload?: CompositionEntry }).payload;
            const label = payload?.label ?? "";
            const percent = payload?.percent ?? 0;
            return [`${value} (${percent}%)`, label];
          }}
        />
        <Bar dataKey="count" fill="#3b82f6" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
