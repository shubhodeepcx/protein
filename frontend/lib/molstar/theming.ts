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
 */
export const COLOR_THEME: Readonly<Record<MolstarColoring, ColorTheme.BuiltIn>> = {
  chain: "chain-id",
  ss: "secondary-structure",
  hydrophobicity: "hydrophobicity",
  plddt: "uncertainty",
  residueType: "residue-name",
};

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
