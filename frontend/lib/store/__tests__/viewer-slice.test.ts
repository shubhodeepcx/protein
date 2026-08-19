import { describe, it, expect, beforeEach } from "vitest";
import { create } from "zustand";
import { createViewerSlice, type ViewerSlice } from "@/lib/store/viewer-slice";

function makeStore() {
  return create<ViewerSlice>()((...a) => createViewerSlice(...a));
}

describe("viewerSlice.resetView", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  it("starts with cartoon representation and chain coloring", () => {
    const state = useTestStore.getState();
    expect(state.representation).toBe("cartoon");
    expect(state.coloring).toBe("chain");
  });

  it("restores representation and coloring to their defaults", () => {
    const { setRepresentation, setColoring, resetView } = useTestStore.getState();
    setRepresentation("spacefill");
    setColoring("plddt");
    expect(useTestStore.getState().representation).toBe("spacefill");
    expect(useTestStore.getState().coloring).toBe("plddt");

    resetView();

    expect(useTestStore.getState().representation).toBe("cartoon");
    expect(useTestStore.getState().coloring).toBe("chain");
  });

  it("does not touch the camera reset tick", () => {
    const { resetCamera, resetView } = useTestStore.getState();
    resetCamera();
    resetCamera();
    expect(useTestStore.getState().cameraResetTick).toBe(2);

    resetView();

    expect(useTestStore.getState().cameraResetTick).toBe(2);
  });
});
