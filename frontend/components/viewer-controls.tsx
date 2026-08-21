"use client";

import { useEffect, useMemo } from "react";
import { useStore } from "@/lib/store";
import {
  REPRESENTATION_OPTIONS,
  coloringOptionsFor,
} from "@/lib/molstar/theming";
import type { Representation, ColoringScheme } from "@/lib/store";

const SELECT_CLASS =
  "h-7 rounded-md border border-zinc-700 bg-zinc-900 px-1.5 text-[11px] text-zinc-300 focus:border-zinc-500 focus:outline-none";

/**
 * Toolbar controls bound to `viewerSlice`. The page owns the effects that push
 * these values into the Mol* imperative API, keeping one direction per effect.
 */
export function ViewerControls({
  disabled,
  hasPlddt = false,
}: {
  disabled?: boolean;
  /**
   * `ProteinSummary.has_plddt` — picks which of the two B-factor-column
   * schemes the coloring menu offers: `pLDDT confidence` when true, plain
   * `B-factor` when false.
   */
  hasPlddt?: boolean;
}) {
  const representation = useStore((s) => s.representation);
  const coloring = useStore((s) => s.coloring);
  const setRepresentation = useStore((s) => s.setRepresentation);
  const setColoring = useStore((s) => s.setColoring);

  const coloringOptions = useMemo(() => coloringOptionsFor(hasPlddt), [hasPlddt]);

  // `coloring` lives in the store and survives navigation, so leaving an
  // AlphaFold model on pLDDT and opening an X-ray entry would leave the select
  // bound to a value it no longer lists — the browser then shows the first
  // option while Mol* still renders the old scheme. Fall back explicitly.
  // Symmetric by construction: `bfactor` carried onto an AlphaFold model is
  // just as unlisted, and resets the same way.
  useEffect(() => {
    if (!coloringOptions.some(([value]) => value === coloring)) {
      setColoring("chain");
    }
  }, [coloringOptions, coloring, setColoring]);

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
        {coloringOptions.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </>
  );
}
