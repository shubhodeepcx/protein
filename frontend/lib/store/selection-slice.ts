import type { StateCreator } from "zustand";

export type SelectionMode = "single" | "range" | "type" | "property";

export interface SelectionSlice {
  /** Residue keys in the form `"<chain>:<resnum>"`, e.g. `"A:123"`. */
  selected: Set<string>;
  mode: SelectionMode;
  /** Toggles a residue key: adds if missing, removes if present. */
  toggleResidue: (key: string) => void;
  /** Replaces the current selection with the given keys. */
  setSelection: (keys: Iterable<string>) => void;
  clearSelection: () => void;
  setMode: (mode: SelectionMode) => void;
}

export const createSelectionSlice: StateCreator<
  SelectionSlice,
  [],
  [],
  SelectionSlice
> = (set) => ({
  selected: new Set<string>(),
  mode: "single",
  toggleResidue: (key) =>
    set((state) => {
      const next = new Set(state.selected);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return { selected: next };
    }),
  setSelection: (keys) => set({ selected: new Set(keys) }),
  clearSelection: () => set({ selected: new Set() }),
  setMode: (mode) => set({ mode }),
});
