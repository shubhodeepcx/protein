"use client";

import { useMemo, useState } from "react";
import {
  COLORING_OPTIONS,
  REPRESENTATION_OPTIONS,
  bfactorColumnSchemeFor,
  type MolstarColoring,
  type MolstarRepresentation,
} from "@/lib/molstar/theming";
import type { CompareProteinRef } from "@/lib/types";
import { CompareViewerPane } from "./compare-viewer-pane";

const SELECT_CLASS =
  "h-7 rounded-md border border-zinc-700 bg-zinc-900 px-1.5 text-[11px] text-zinc-300 focus:border-zinc-500 focus:outline-none";

/**
 * The coloring schemes that mean the same thing on both structures.
 *
 * `plddt` and `bfactor` both read the B-factor column, and which of them is
 * truthful depends on `has_plddt`. When the two structures disagree — the
 * predicted-vs-experimental pair A3 is built around — one shared select cannot
 * offer either without mislabelling one side, so both drop out and the four
 * structure-independent schemes remain. When they agree, the correct one is
 * offered to both.
 */
export function sharedColoringOptions(
  hasPlddtA: boolean,
  hasPlddtB: boolean,
): ReadonlyArray<readonly [MolstarColoring, string]> {
  if (hasPlddtA !== hasPlddtB) {
    return COLORING_OPTIONS.filter(
      ([value]) => value !== "plddt" && value !== "bfactor",
    );
  }
  const hidden = bfactorColumnSchemeFor(!hasPlddtA);
  return COLORING_OPTIONS.filter(([value]) => value !== hidden);
}

/**
 * The two Mol* viewers, side by side, under one representation/coloring select.
 *
 * The controls are shared on purpose: comparing two structures rendered in
 * different representations compares the rendering, not the structures. They
 * are local state rather than `viewerSlice`, so opening `/compare` cannot
 * disturb the single-protein viewer's settings.
 */
export function CompareViewers({
  a,
  b,
}: {
  a: CompareProteinRef;
  b: CompareProteinRef;
}) {
  const [representation, setRepresentation] =
    useState<MolstarRepresentation>("cartoon");
  const [coloring, setColoring] = useState<MolstarColoring>("chain");

  const coloringOptions = useMemo(
    () => sharedColoringOptions(a.has_plddt, b.has_plddt),
    [a.has_plddt, b.has_plddt],
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h2 className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
          Structures
        </h2>
        <div className="ml-auto flex items-center gap-1.5">
          <select
            aria-label="Representation"
            title="Representation, applied to both viewers"
            className={SELECT_CLASS}
            value={representation}
            onChange={(e) =>
              setRepresentation(e.target.value as MolstarRepresentation)
            }
          >
            {REPRESENTATION_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Coloring"
            title="Coloring, applied to both viewers"
            className={SELECT_CLASS}
            value={coloring}
            onChange={(e) => setColoring(e.target.value as MolstarColoring)}
          >
            {coloringOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        <CompareViewerPane
          protein={a}
          side="A"
          representation={representation}
          coloring={coloring}
        />
        <CompareViewerPane
          protein={b}
          side="B"
          representation={representation}
          coloring={coloring}
        />
      </div>
    </div>
  );
}
