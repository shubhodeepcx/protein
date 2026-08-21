import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import React from "react";

/**
 * Regression test for the mount/teardown race in `molstar-viewer.tsx`.
 *
 * `createViewerPlugin` is async and takes ownership of a React root on the
 * container div. React's cleanup, however, is synchronous — so under
 * StrictMode's double-invoke (mount → cleanup → mount), the teardown used to
 * fire while the first plugin was still constructing. `pluginInstance` was
 * still null at that point, so nothing was disposed, and the second mount then
 * called `ReactDOMClient.createRoot()` on a container that already had one:
 *
 *   "You are calling ReactDOMClient.createRoot() on a container that has
 *    already been passed to createRoot() before."
 *
 * The fix chains each init behind the previous cycle's teardown. This test
 * pins that ordering — it fails if the chaining is removed.
 *
 * Mol* itself is a trusted library and is never unit-tested here; the plugin
 * module is mocked so no WebGL is required.
 */

/** Resolvers for the pending `createViewerPlugin` calls, newest last. */
const pending: Array<() => void> = [];
/** How many plugins are constructed-but-not-yet-disposed at any instant. */
let live = 0;
let createCalls = 0;
/**
 * Constructions started but not yet settled. This is the number that matters:
 * `createViewerPlugin` takes a React root on the container the moment it is
 * called, so two overlapping calls on one container is exactly the bug.
 */
let inFlight = 0;
let maxInFlight = 0;

const disposeSpy = vi.fn();

vi.mock("@/lib/molstar/plugin", () => ({
  createViewerPlugin: vi.fn(
    () =>
      new Promise((resolve) => {
        createCalls += 1;
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        pending.push(() => {
          inFlight -= 1;
          live += 1;
          resolve({
            dispose: () => {
              live -= 1;
              disposeSpy();
            },
            behaviors: {
              interaction: { click: { subscribe: () => ({ unsubscribe() {} }) } },
            },
          });
        });
      }),
  ),
}));

vi.mock("molstar/lib/mol-plugin/commands", () => ({
  PluginCommands: { Camera: { Reset: vi.fn() } },
}));

vi.mock("@/lib/molstar/actions", () => ({
  applyColoring: vi.fn(),
  applyRepresentation: vi.fn(),
  applySelection: vi.fn(),
  loadStructureInto: vi.fn(async () => null),
}));

vi.mock("@/lib/molstar/residue-index", () => ({
  buildResidueIndex: vi.fn(() => ({})),
  warnOnResidueDrift: vi.fn(),
  resolveResidueLocus: vi.fn(),
  residueClickPayload: vi.fn(),
  EMPTY_RESIDUE_INDEX: {},
}));

/** Settle every queued `createViewerPlugin` promise, in call order. */
function flushPending() {
  while (pending.length) pending.shift()!();
}

/**
 * Let queued microtasks run. Construction is now chained behind the previous
 * teardown promise, so `createViewerPlugin` is reached a tick after render
 * rather than synchronously — that deferral is the fix, not a flaw.
 */
const tick = () => new Promise((r) => setTimeout(r, 0));

describe("MolstarViewer mount/teardown lifecycle", () => {
  beforeEach(() => {
    pending.length = 0;
    live = 0;
    inFlight = 0;
    maxInFlight = 0;
    createCalls = 0;
    disposeSpy.mockClear();
  });

  it("never has two plugin constructions in flight on the same container", async () => {
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");

    // StrictMode double-invokes the effect on the SAME instance and the SAME
    // container div: mount → cleanup → mount. That shared container is why a
    // second createRoot() collides with the first.
    render(
      <React.StrictMode>
        <MolstarViewer />
      </React.StrictMode>,
    );

    // Drain: each settled construction lets the parked next cycle proceed.
    for (let i = 0; i < 6; i += 1) {
      await tick();
      flushPending();
    }
    await tick();

    // The assertion that carries the fix. Without the teardown chaining the
    // second cycle starts constructing while the first is still pending, this
    // reaches 2, and the browser throws the duplicate-createRoot error.
    expect(maxInFlight).toBe(1);
    expect(createCalls).toBeGreaterThanOrEqual(1);
    cleanup();
  });

  it("disposes the plugin created by a cycle that was torn down mid-construction", async () => {
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");

    const view = render(<MolstarViewer />);
    await tick();
    view.unmount();
    flushPending();

    // The plugin resolved after unmount; it must still be disposed, not leaked.
    await waitFor(() => expect(live).toBe(0));
    cleanup();
  });
});
