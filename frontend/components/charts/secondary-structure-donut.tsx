"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import type { SecondaryStructurePercentages } from "@/lib/types";

const COLORS = { helix: "#f59e0b", sheet: "#06b6d4", coil: "#71717a" } as const;

export function SecondaryStructureDonut({
  data,
}: {
  data: SecondaryStructurePercentages;
}) {
  const slices = [
    { name: "Helix", value: data.helix, fill: COLORS.helix },
    { name: "Sheet", value: data.sheet, fill: COLORS.sheet },
    { name: "Coil", value: data.coil, fill: COLORS.coil },
  ].filter((s) => s.value > 0);

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={slices}
          dataKey="value"
          nameKey="name"
          innerRadius={42}
          outerRadius={66}
          strokeWidth={1}
          stroke="#18181b"
        >
          {slices.map((s) => (
            <Cell key={s.name} fill={s.fill} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }}
          itemStyle={{ color: "#fafafa" }}
          formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
        />
        <Legend
          iconSize={8}
          wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
          formatter={(value, entry) => {
            const v = (entry.payload as { value: number })?.value ?? 0;
            return `${value} (${(v * 100).toFixed(0)}%)`;
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
