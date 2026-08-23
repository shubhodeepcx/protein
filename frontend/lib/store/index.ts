"use client";

import { create } from "zustand";
import { createBlastSlice, type BlastSlice } from "./blast-slice";
import { createProteinSlice, type ProteinSlice } from "./protein-slice";
import { createSelectionSlice, type SelectionSlice } from "./selection-slice";
import { createViewerSlice, type ViewerSlice } from "./viewer-slice";

export type Store = ProteinSlice & SelectionSlice & ViewerSlice & BlastSlice;

/**
 * Combined Zustand store composing the three slices defined in spec section 4.2,
 * plus the P8 BLAST/similarity slice.
 *
 * Slices stay in their own files so they remain independently unit-testable;
 * this `create` call wires them into a single hook.
 */
export const useStore = create<Store>()((...a) => ({
  ...createProteinSlice(...a),
  ...createSelectionSlice(...a),
  ...createViewerSlice(...a),
  ...createBlastSlice(...a),
}));

export type { BlastSlice } from "./blast-slice";
export type { ProteinSlice } from "./protein-slice";
export type { SelectionSlice, SelectionMode } from "./selection-slice";
export type {
  ViewerSlice,
  Representation,
  ColoringScheme,
} from "./viewer-slice";
