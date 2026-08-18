"use client";

import { useStore } from "@/lib/store";
import {
  COLORING_OPTIONS,
  REPRESENTATION_OPTIONS,
} from "@/lib/molstar/theming";
import type { Representation, ColoringScheme } from "@/lib/store";

const SELECT_CLASS =
  "h-7 rounded-md border border-zinc-700 bg-zinc-900 px-1.5 text-[11px] text-zinc-300 focus:border-zinc-500 focus:outline-none";

/**
 * Toolbar controls bound to `viewerSlice`. The page owns the effects that push
 * these values into the Mol* imperative API, keeping one direction per effect.
 */
export function ViewerControls({ disabled }: { disabled?: boolean }) {
  const representation = useStore((s) => s.representation);
  const coloring = useStore((s) => s.coloring);
  const setRepresentation = useStore((s) => s.setRepresentation);
  const setColoring = useStore((s) => s.setColoring);

  return (
    <>
      <select
        aria-label="Representation"
        title="Representation"
        className={SELECT_CLASS}
        disabled={disabled}
        value={representation}
        onChange={(e) => setRepresentation(e.target.value as Representation)}
      >
        {REPRESENTATION_OPTIONS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      <select
        aria-label="Coloring"
        title="Coloring"
        className={SELECT_CLASS}
        disabled={disabled}
        value={coloring}
        onChange={(e) => setColoring(e.target.value as ColoringScheme)}
      >
        {COLORING_OPTIONS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </>
  );
}
