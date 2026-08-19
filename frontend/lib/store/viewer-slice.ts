import type { StateCreator } from "zustand";

export type Representation =
  | "cartoon"
  | "surface"
  | "stick"
  | "ball-stick"
  | "spacefill";

export type ColoringScheme =
  | "chain"
  | "ss"
  | "hydrophobicity"
  | "plddt"
  | "residueType";

export interface ViewerSlice {
  representation: Representation;
  coloring: ColoringScheme;
  /**
   * Incremented to signal that the viewer should reset its camera. Components
   * subscribe to this counter rather than holding an imperative ref to Mol*.
   */
  cameraResetTick: number;
  setRepresentation: (representation: Representation) => void;
  setColoring: (coloring: ColoringScheme) => void;
  resetCamera: () => void;
  /**
   * Restores representation/coloring to their defaults. Called when leaving a
   * protein (route change) so the next one doesn't inherit e.g. "spacefill" +
   * "plddt" from a completely unrelated structure.
   */
  resetView: () => void;
}

const DEFAULT_REPRESENTATION: Representation = "cartoon";
const DEFAULT_COLORING: ColoringScheme = "chain";

export const createViewerSlice: StateCreator<ViewerSlice, [], [], ViewerSlice> = (
  set,
) => ({
  representation: DEFAULT_REPRESENTATION,
  coloring: DEFAULT_COLORING,
  cameraResetTick: 0,
  setRepresentation: (representation) => set({ representation }),
  setColoring: (coloring) => set({ coloring }),
  resetCamera: () => set((state) => ({ cameraResetTick: state.cameraResetTick + 1 })),
  resetView: () =>
    set({ representation: DEFAULT_REPRESENTATION, coloring: DEFAULT_COLORING }),
});
