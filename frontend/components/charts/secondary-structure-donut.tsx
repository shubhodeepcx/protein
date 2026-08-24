"use client";

import { AlertTriangle } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import type { SecondaryStructurePercentages } from "@/lib/types";

const COLORS = { helix: "#f59e0b", sheet: "#06b6d4", coil: "#71717a" } as const;

/**
 * Ring colour for "the file never said". Deliberately not one of the three
 * data colours — an absence of annotation must not borrow the visual language
 * of a measurement.
 */
const UNKNOWN_COLOR = "#3f3f46";

export const NOT_ANNOTATED_LABEL = "Not annotated";

export interface DonutSlice {
  name: string;
  /** Fraction of the ring. For the placeholder this is a full turn, not a datum. */
  value: number;
  fill: string;
}

/**
 * Ring slices for one secondary-structure split.
 *
 * When `available` is false the backend still sends a numerically valid
 * `helix: 0, sheet: 0, coil: 1` split — it has nothing else to send — so a
 * consumer that ignores the flag draws a solid coil ring and a legend reading
 * "Coil (100%)". That is a claim the data never made. In that case this
 * returns a single neutral placeholder slice carrying no percentage instead.
 */
export function secondaryStructureSlices(
  data: SecondaryStructurePercentages,
): DonutSlice[] {
  if (!data.available) {
    return [{ name: NOT_ANNOTATED_LABEL, value: 1, fill: UNKNOWN_COLOR }];
  }
  return [
    { name: "Helix", value: data.helix, fill: COLORS.helix },
    { name: "Sheet", value: data.sheet, fill: COLORS.sheet },
    { name: "Coil", value: data.coil, fill: COLORS.coil },
  ].filter((s) => s.value > 0);
}

export function SecondaryStructureDonut({
  data,
}: {
  data: SecondaryStructurePercentages;
}) {
  const available = data.available;
  const slices = secondaryStructureSlices(data);

  return (
    <div className="flex flex-col gap-1.5">
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
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              fontSize: 11,
            }}
            itemStyle={{ color: "#fafafa" }}
            formatter={(value: number) =>
              available ? `${(value * 100).toFixed(1)}%` : "no assignment"
            }
          />
          <Legend
            iconSize={8}
            wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
            formatter={(value, entry) => {
              if (!available) return value;
              const v = (entry.payload as { value: number })?.value ?? 0;
              return `${value} (${(v * 100).toFixed(0)}%)`;
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Same treatment the comparison table gives `available_a` / `available_b`
          (see `app/compare/compare-metrics.tsx`): keep the visual, but state
          plainly that it is not a measurement. */}
      {!available && (
        <p
          data-testid="ss-unavailable-warning"
          role="status"
          className="flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-amber-400"
        >
          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>
            This structure declares no secondary structure, so the ring above is
            an all-coil placeholder and not a measurement. AlphaFold models
            carry no helix/sheet assignment.
          </span>
        </p>
      )}
    </div>
  );
}
