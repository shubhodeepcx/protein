import { describe, it, expect, beforeEach } from "vitest";
import { create } from "zustand";
import {
  createSelectionSlice,
  type SelectionSlice,
} from "@/lib/store/selection-slice";

function makeStore() {
  return create<SelectionSlice>()((...a) => createSelectionSlice(...a));
}

describe("selectionSlice.toggleResidue", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  it("starts with an empty selection in single mode", () => {
    const state = useTestStore.getState();
    expect(state.selected.size).toBe(0);
    expect(state.mode).toBe("single");
  });

  it("adds a residue key when toggled the first time", () => {
    useTestStore.getState().toggleResidue("A:123");
    expect(useTestStore.getState().selected.has("A:123")).toBe(true);
  });

  it("removes a residue key when toggled a second time", () => {
    const { toggleResidue } = useTestStore.getState();
    toggleResidue("A:123");
    toggleResidue("A:123");
    expect(useTestStore.getState().selected.has("A:123")).toBe(false);
    expect(useTestStore.getState().selected.size).toBe(0);
  });

  it("supports multiple independent keys", () => {
    const { toggleResidue } = useTestStore.getState();
    toggleResidue("A:1");
    toggleResidue("A:2");
    toggleResidue("B:5");
    const selected = useTestStore.getState().selected;
    expect(selected.size).toBe(3);
    expect(selected.has("A:1")).toBe(true);
    expect(selected.has("A:2")).toBe(true);
    expect(selected.has("B:5")).toBe(true);
  });

  it("setSelection replaces the current set", () => {
    const { toggleResidue, setSelection } = useTestStore.getState();
    toggleResidue("A:1");
    setSelection(["B:10", "B:11"]);
    const selected = useTestStore.getState().selected;
    expect(selected.size).toBe(2);
    expect(selected.has("A:1")).toBe(false);
    expect(selected.has("B:10")).toBe(true);
  });

  it("clearSelection empties the set", () => {
    const { toggleResidue, clearSelection } = useTestStore.getState();
    toggleResidue("A:1");
    toggleResidue("A:2");
    clearSelection();
    expect(useTestStore.getState().selected.size).toBe(0);
  });

  it("setMode updates the selection mode", () => {
    useTestStore.getState().setMode("range");
    expect(useTestStore.getState().mode).toBe("range");
  });
});
