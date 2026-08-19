/**
 * Imperative Mol* operations, kept out of the React component so
 * `components/molstar-viewer.tsx` stays a thin ref-forwarding shell.
 *
 * Every function here takes an already-created plugin; callers are responsible
 * for the null check on the asynchronously created instance.
 */

import type { PluginContext } from "molstar/lib/mol-plugin/context";
import { StructureElement, type Structure } from "molstar/lib/mol-model/structure";
import { createStructureRepresentationParams } from "molstar/lib/mol-plugin-state/helpers/structure-representation-params";
import { keysToLoci, type ResidueIndexMap } from "@/lib/molstar/residue-index";
import {
  COLOR_THEME,
  REPRESENTATION_SPEC,
  colorParamsFor,
  type MolstarColoring,
  type MolstarRepresentation,
} from "@/lib/molstar/theming";

export type MolstarFormat = "pdb" | "mmcif";

/**
 * Downloads, parses and renders a structure, returning the resulting
 * `Structure` (or `null` if the hierarchy came back empty).
 *
 * `isStale` is checked after every await. Each step here is a network or state
 * transaction, so navigating away mid-load would otherwise let the continuation
 * parse and apply a preset against a disposed plugin. Callers supply a check
 * that covers both disposal and a newer load having superseded this one.
 */
export async function loadStructureInto(
  plugin: PluginContext,
  url: string,
  format: MolstarFormat,
  isStale: () => boolean = () => false,
): Promise<Structure | null> {
  await plugin.clear();
  if (isStale()) return null;

  const data = await plugin.builders.data.download(
    { url, isBinary: false },
    { state: { isGhost: true } },
  );
  if (isStale()) return null;

  const trajectory = await plugin.builders.structure.parseTrajectory(
    data,
    format === "mmcif" ? "mmcif" : "pdb",
  );
  if (isStale()) return null;

  await plugin.builders.structure.hierarchy.applyPreset(trajectory, "default");
  if (isStale()) return null;

  return (
    plugin.managers.structure.hierarchy.current.structures[0]?.cell.obj?.data ??
    null
  );
}

/**
 * Store -> Mol*. Writes to the selection manager only; it never re-emits a
 * click event, so this direction cannot ping-pong back into the store.
 */
export function applySelection(
  plugin: PluginContext,
  structure: Structure,
  keys: readonly string[],
  index: ResidueIndexMap,
): void {
  const loci = keys.length === 0 ? null : keysToLoci(structure, keys, index);
  // An empty loci must clear rather than "select nothing", which would leave
  // stale markers on screen.
  if (!loci || StructureElement.Loci.isEmpty(loci)) {
    plugin.managers.structure.selection.clear();
    return;
  }
  plugin.managers.structure.selection.fromLoci("set", loci);
}

export function applyRepresentation(
  plugin: PluginContext,
  type: MolstarRepresentation,
): void {
  const spec = REPRESENTATION_SPEC[type];

  for (const s of plugin.managers.structure.hierarchy.current.structures) {
    const data = s.cell.obj?.data;
    const params =
      spec.sizeAspectRatio === undefined
        ? createStructureRepresentationParams(plugin, data, { type: spec.type })
        : createStructureRepresentationParams(plugin, data, {
            type: "ball-and-stick",
            typeParams: { sizeAspectRatio: spec.sizeAspectRatio },
          });
    for (const component of s.components) {
      const pivot = component.representations[0];
      if (!pivot) continue;
      void plugin.managers.structure.component.updateRepresentations(
        [component],
        pivot,
        params,
      );
    }
  }
}

export interface ColoringOptions {
  /**
   * `ProteinSummary.has_plddt` — true when the B-factor column holds AlphaFold
   * pLDDT rather than crystallographic temperature factors. It flips the
   * `uncertainty` theme's domain so high confidence reads blue; see
   * `PLDDT_COLOR_DOMAIN`.
   *
   * Required, and deliberately so: the shipped inversion bug was an *implicit*
   * assumption that the B-factor column meant the same thing for every
   * structure. Making every caller answer the question makes dropping the
   * answer a type error rather than a silently wrong render.
   */
  readonly hasPlddt: boolean;
}

export function applyColoring(
  plugin: PluginContext,
  scheme: MolstarColoring,
  options: ColoringOptions,
): void {
  const color = COLOR_THEME[scheme];
  const colorParams = colorParamsFor(scheme, options.hasPlddt);
  // Passing `colorParams: undefined` is not the same as omitting it — Mol*
  // merges the key in and would clear any theme defaults — so build the two
  // shapes separately.
  const params = colorParams ? { color, colorParams } : { color };
  for (const s of plugin.managers.structure.hierarchy.current.structures) {
    void plugin.managers.structure.component.updateRepresentationsTheme(
      s.components,
      params,
    );
  }
}
