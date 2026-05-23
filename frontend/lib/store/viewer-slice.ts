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
}

export const createViewerSlice: StateCreator<ViewerSlice, [], [], ViewerSlice> = (
  set,
) => ({
  representation: "cartoon",
  coloring: "chain",
  cameraResetTick: 0,
  setRepresentation: (representation) => set({ representation }),
  setColoring: (coloring) => set({ coloring }),
  resetCamera: () => set((state) => ({ cameraResetTick: state.cameraResetTick + 1 })),
});
