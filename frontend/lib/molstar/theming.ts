/**
 * Maps ProteoLens' representation / coloring vocabulary (from `viewerSlice`)
 * onto Mol*'s registry names.
 *
 * Kept separate from the viewer component so the mapping is a plain data table
 * that can be read and unit-tested without touching WebGL.
 */

import type { StructureRepresentationRegistry } from "molstar/lib/mol-repr/structure/registry";
import type { ColorTheme } from "molstar/lib/mol-theme/color";

export type MolstarRepresentation =
  | "cartoon"
  | "surface"
  | "stick"
  | "ball-stick"
  | "spacefill";

export type MolstarColoring =
  | "chain"
  | "ss"
  | "hydrophobicity"
  | "plddt"
  | "residueType";

export interface RepresentationSpec {
  readonly type: StructureRepresentationRegistry.BuiltIn;
  /** `sizeAspectRatio: 1` collapses ball-and-stick down to plain sticks. */
  readonly sizeAspectRatio?: number;
}

export const REPRESENTATION_SPEC: Readonly<
  Record<MolstarRepresentation, RepresentationSpec>
> = {
  cartoon: { type: "cartoon" },
  surface: { type: "molecular-surface" },
  stick: { type: "ball-and-stick", sizeAspectRatio: 1 },
  "ball-stick": { type: "ball-and-stick" },
  spacefill: { type: "spacefill" },
};

/**
 * Color-theme names from `ColorTheme.BuiltIn`.
 *
 * `plddt` maps to `uncertainty` (Mol*'s B-factor theme) on purpose: the
 * dedicated `plddt-confidence` theme lives in the model-archive extension and
 * needs the mmCIF `ma_qa_metric_local` category, which uploaded AlphaFold *PDB*
 * files do not carry. Those files put pLDDT in the B-factor column, which is
 * exactly what `uncertainty` reads.
 *
 * That reuse comes with one catch the domain below exists to undo — see
 * `PLDDT_COLOR_DOMAIN`.
 */
export const COLOR_THEME: Readonly<Record<MolstarColoring, ColorTheme.BuiltIn>> = {
  chain: "chain-id",
  ss: "secondary-structure",
  hydrophobicity: "hydrophobicity",
  plddt: "uncertainty",
  residueType: "residue-name",
};

/**
 * The `uncertainty` theme's domain, INVERTED, for structures whose B-factor
 * column holds pLDDT.
 *
 * Mol*'s `uncertainty` theme builds
 * `ColorScale.create({ reverse: true, domain: [0, 100], listOrName: 'red-white-blue' })`.
 * `reverse` flips the list to blue-white-red, so under the default domain the
 * value 0 renders blue and 100 renders red.
 *
 * For a crystallographic B-factor that is exactly right: a low B means a
 * well-ordered atom, so well-ordered reads blue. pLDDT runs the other way —
 * **high** means confident — so the same scale paints an AlphaFold model's
 * confident core red and its disordered tails blue, the inverse of the
 * convention every AlphaFold viewer uses.
 *
 * Flipping the domain endpoints fixes it without touching the color list.
 * `ColorScale` computes `diff = max - min`, which simply goes negative here, so
 * 100 lands at scale position 0 (blue), 50 in the middle (white), and 0 at the
 * far end (red).
 *
 * The orientation — `domain[0] > domain[1]` — is the load-bearing part, and is
 * pinned by `lib/molstar/__tests__/theming.test.ts`. Do not "tidy" it into
 * ascending order.
 */
export const PLDDT_COLOR_DOMAIN: readonly [number, number] = [100, 0];

/** The subset of Mol* color-theme params ProteoLens sets. */
export interface ColorThemeParams {
  readonly domain: readonly [number, number];
}

/**
 * Extra theme params for a scheme, or `undefined` to take Mol*'s defaults.
 *
 * `hasPlddt` mirrors `ProteinSummary.has_plddt`: the `plddt` scheme drives the
 * shared `uncertainty` theme, so the domain must only be inverted when the
 * B-factor column really holds pLDDT. Inverting it for an experimental
 * structure would break B-factor coloring in exactly the same way.
 */
export function colorParamsFor(
  scheme: MolstarColoring,
  hasPlddt: boolean,
): ColorThemeParams | undefined {
  if (scheme === "plddt" && hasPlddt) return { domain: PLDDT_COLOR_DOMAIN };
  return undefined;
}

export const REPRESENTATION_OPTIONS: ReadonlyArray<
  readonly [MolstarRepresentation, string]
> = [
  ["cartoon", "Cartoon"],
  ["surface", "Surface"],
  ["stick", "Stick"],
  ["ball-stick", "Ball & stick"],
  ["spacefill", "Spacefill"],
];

export const COLORING_OPTIONS: ReadonlyArray<readonly [MolstarColoring, string]> =
  [
    ["chain", "Chain"],
    ["ss", "Secondary structure"],
    ["hydrophobicity", "Hydrophobicity"],
    ["plddt", "pLDDT / B-factor"],
    ["residueType", "Residue type"],
  ];

