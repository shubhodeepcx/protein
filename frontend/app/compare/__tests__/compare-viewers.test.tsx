import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import React from "react";

/**
 * Two Mol* viewers on one page — the case `/compare` puts `MolstarViewer` in.
 *
 * `components/__tests__/molstar-viewer-lifecycle.test.tsx` already pins the
 * StrictMode mount → cleanup → mount race on ONE container. This file asks the
 * different question the comparison view raises: does a second instance,
 * mounting and tearing down alongside the first, interfere with it?
 *
 * It should not, and for a structural reason rather than a timing one — every
 * piece of `MolstarViewer`'s mutable state (`pluginRef`, `structureRef`,
 * `indexRef`, `loadSeqRef`, and crucially `teardownRef`, the promise that
 * serialises mount/teardown cycles) lives in a `useRef`, which is per-instance.
 * These tests pin that: a shared module-level teardown promise, or a shared
 * plugin ref, would fail them.
 *
 * Mol* itself is a trusted library and is never unit-tested here; the plugin
 * module is mocked so no WebGL is required.
 */

interface PluginHandle {
  id: number;
  target: HTMLElement;
  dispose: () => void;
  behaviors: { interaction: { click: { subscribe: () => { unsubscribe(): void } } } };
}

/** Queued resolvers for pending `createViewerPlugin` calls, in call order. */
const pending: Array<() => void> = [];
/** Constructions started but not settled, keyed by the container they took. */
const inFlightByTarget = new Map<HTMLElement, number>();
/** The worst simultaneous in-flight count any single container ever saw. */
let maxInFlightPerTarget = 0;
/** Plugins constructed but not yet disposed. */
let live = 0;
let nextPluginId = 0;
const targetsSeen: HTMLElement[] = [];
const created: PluginHandle[] = [];

vi.mock("@/lib/molstar/plugin", () => ({
  createViewerPlugin: vi.fn(
    (target: HTMLElement) =>
      new Promise<PluginHandle>((resolve) => {
        targetsSeen.push(target);
        const now = (inFlightByTarget.get(target) ?? 0) + 1;
        inFlightByTarget.set(target, now);
        maxInFlightPerTarget = Math.max(maxInFlightPerTarget, now);

        pending.push(() => {
          inFlightByTarget.set(target, (inFlightByTarget.get(target) ?? 1) - 1);
          live += 1;
          const handle: PluginHandle = {
            id: (nextPluginId += 1),
            target,
            dispose: () => {
              live -= 1;
            },
            behaviors: {
              interaction: { click: { subscribe: () => ({ unsubscribe() {} }) } },
            },
          };
          created.push(handle);
          resolve(handle);
        });
      }),
  ),
}));

vi.mock("molstar/lib/mol-plugin/commands", () => ({
  PluginCommands: { Camera: { Reset: vi.fn() } },
}));

const loadStructureInto = vi.fn(async () => null);

vi.mock("@/lib/molstar/actions", () => ({
  applyColoring: vi.fn(),
  applyRepresentation: vi.fn(),
  applySelection: vi.fn(),
  loadStructureInto: (...args: unknown[]) => loadStructureInto(...(args as [])),
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

/** Construction is chained behind the previous teardown, so it lands a tick later. */
const tick = () => new Promise((r) => setTimeout(r, 0));

/** Drain repeatedly: each settled construction releases a parked next cycle. */
async function drain(rounds = 8) {
  for (let i = 0; i < rounds; i += 1) {
    await tick();
    flushPending();
  }
  await tick();
}

describe("two MolstarViewer instances on one page", () => {
  beforeEach(() => {
    pending.length = 0;
    inFlightByTarget.clear();
    targetsSeen.length = 0;
    created.length = 0;
    maxInFlightPerTarget = 0;
    live = 0;
    nextPluginId = 0;
    loadStructureInto.mockClear();
  });

  it("gives each viewer its own container and never overlaps constructions on one", async () => {
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");

    render(
      <React.StrictMode>
        <div>
          <MolstarViewer />
          <MolstarViewer />
        </div>
      </React.StrictMode>,
    );

    await drain();

    // Two instances, two container divs. If they shared one, the duplicate
    // `createRoot()` this whole mechanism exists to prevent would be back.
    const distinctTargets = new Set(targetsSeen);
    expect(distinctTargets.size).toBe(2);

    // The assertion that carries the fix: per container, never two overlapping
    // constructions — even though the two instances' cycles interleave.
    expect(maxInFlightPerTarget).toBe(1);

    cleanup();
  });

  it("disposes both plugins when the page unmounts", async () => {
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");

    const view = render(
      <div>
        <MolstarViewer />
        <MolstarViewer />
      </div>,
    );
    await tick();
    flushPending();
    await waitFor(() => expect(live).toBe(2));

    view.unmount();
    flushPending();

    // Neither instance may leak a WebGL context when the comparison closes.
    await waitFor(() => expect(live).toBe(0));
    cleanup();
  });

  it("routes each viewer's loadStructure to its own plugin", async () => {
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");
    const { createRef } = React;

    const refA = createRef<import("@/components/molstar-viewer").MolstarViewerRef>();
    const refB = createRef<import("@/components/molstar-viewer").MolstarViewerRef>();

    render(
      <div>
        <MolstarViewer ref={refA} />
        <MolstarViewer ref={refB} />
      </div>,
    );
    await tick();
    flushPending();
    await waitFor(() => expect(created.length).toBe(2));

    await refA.current!.loadStructure("/a.pdb", "pdb");
    await refB.current!.loadStructure("/b.cif", "mmcif");

    expect(loadStructureInto).toHaveBeenCalledTimes(2);
    const [callA, callB] = loadStructureInto.mock.calls as unknown as [
      [PluginHandle, string, string, () => boolean],
      [PluginHandle, string, string, () => boolean],
    ];

    // Distinct plugins, distinct urls, and each url went to the plugin whose
    // container belongs to that instance. A shared `pluginRef` would send both
    // loads to whichever viewer mounted last, and the B pane would silently
    // render A's structure.
    expect(callA[0].id).not.toBe(callB[0].id);
    expect(callA[1]).toBe("/a.pdb");
    expect(callB[1]).toBe("/b.cif");
    expect(callA[2]).toBe("pdb");
    expect(callB[2]).toBe("mmcif");
    expect(callA[0].target).not.toBe(callB[0].target);

    cleanup();
  });

  it("does not block one viewer's remount behind the other's pending teardown", async () => {
    /**
     * The teardown promise is what serialises a single viewer's mount/teardown
     * cycles. It must be per-instance: shared, one pane's unfinished teardown
     * would hold the other pane's plugin construction hostage, and on
     * `/compare` that is a viewer that never renders at all.
     *
     * Setup: settle only B's construction, leaving A's pending, then unmount A
     * so its teardown chains behind a promise that will not settle. B is then
     * remounted. With per-instance refs B constructs immediately; with a
     * shared one it waits on A forever.
     */
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");

    // B is FIRST in the tree on purpose. React runs cleanups in tree order, so
    // B's teardown is written before A's — meaning a single shared slot ends up
    // holding A's never-settling promise when B's new effect goes to wait on
    // it. With B last, B's own (settled) teardown would overwrite A's and mask
    // the sharing.
    function Page({ showA, bKey }: { showA: boolean; bKey: string }) {
      return (
        <div>
          <MolstarViewer key={bKey} />
          {showA && <MolstarViewer />}
        </div>
      );
    }

    const view = render(<Page showA bKey="b1" />);
    await tick();

    // Settle B's construction only — A's stays in flight. B mounts first, so
    // B's resolver is the one queued first.
    expect(pending.length).toBe(2);
    pending.shift()!();
    await waitFor(() => expect(created.length).toBe(1));
    const startedBefore = targetsSeen.length;

    // A and B change together: A goes away mid-construction, so its teardown
    // chains on a promise still sitting in `pending` and can never settle,
    // while B remounts and must construct regardless.
    view.rerender(<Page showA={false} bKey="b2" />);

    // Ticks only — deliberately NOT `drain`, which would settle A's stuck
    // construction and release the very teardown this test needs left pending.
    // `targetsSeen` counts constructions STARTED, so it moves without a flush.
    for (let i = 0; i < 4; i += 1) await tick();

    expect(targetsSeen.length).toBeGreaterThan(startedBefore);

    // Let A's construction settle so the mock's bookkeeping unwinds cleanly.
    flushPending();
    await tick();
    cleanup();
  });

  it("keeps each viewer's load token independent", async () => {
    const { default: MolstarViewer } = await import("@/components/molstar-viewer");
    const { createRef } = React;

    const refA = createRef<import("@/components/molstar-viewer").MolstarViewerRef>();
    const refB = createRef<import("@/components/molstar-viewer").MolstarViewerRef>();

    render(
      <div>
        <MolstarViewer ref={refA} />
        <MolstarViewer ref={refB} />
      </div>,
    );
    await tick();
    flushPending();
    await waitFor(() => expect(created.length).toBe(2));

    // Start A's load, let B's whole load run inside it, then let A finish.
    // A's `isStale()` must still say "current": B's load took B's token, not A's.
    let releaseA: () => void = () => {};
    const aInFlight = new Promise<null>((resolve) => {
      releaseA = () => resolve(null);
    });
    let staleDuringA: boolean | null = null;

    loadStructureInto.mockImplementationOnce(
      (async (
        _plugin: PluginHandle,
        _url: string,
        _format: string,
        isStale: () => boolean,
      ) => {
        const result = await aInFlight;
        staleDuringA = isStale();
        return result;
      }) as unknown as () => Promise<null>,
    );

    const loadA = refA.current!.loadStructure("/a.pdb", "pdb");
    await refB.current!.loadStructure("/b.cif", "mmcif");
    releaseA();
    await loadA;

    expect(staleDuringA).toBe(false);
    cleanup();
  });
});
