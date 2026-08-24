import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { create } from "zustand";

import { createProteinSlice, type ProteinSlice } from "@/lib/store/protein-slice";
import type { FunctionalRegions } from "@/lib/types";

function makeStore() {
  return create<ProteinSlice>()((...a) => createProteinSlice(...a));
}

function payload(patch: Partial<FunctionalRegions> = {}): FunctionalRegions {
  return {
    id: "id",
    accession: "P00698",
    accession_resolved: true,
    resolution_note: "note",
    chain_mappings: [],
    active_sites: [],
    binding_sites: [],
    other_sites: [],
    dna_binding: [],
    ligands: [],
    contact_cutoff: 4.0,
    surface: [],
    surface_note: "",
    priority_residues: [],
    unlocated_sites: 0,
    notes: [],
    ...patch,
  };
}

/** One deferred fetch response per call, resolved by the test. */
function deferredFetch() {
  const resolvers: ((body: FunctionalRegions) => void)[] = [];
  const fetchMock = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        resolvers.push((body) =>
          resolve(new Response(JSON.stringify(body), { status: 200 })),
        );
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return { resolvers, fetchMock };
}

describe("proteinSlice.loadFunctional", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("requests the functional-regions endpoint for the given id", async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        urls.push(String(input));
        return new Response(JSON.stringify(payload()), { status: 200 });
      }),
    );

    await useTestStore.getState().loadFunctional("abc");

    expect(urls[0]).toContain("/api/proteins/abc/functional-regions");
  });

  it("stores the payload and clears the loading flag", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(payload({ contact_cutoff: 4.0 })), {
            status: 200,
          }),
      ),
    );

    await useTestStore.getState().loadFunctional("abc");

    expect(useTestStore.getState().functional?.contact_cutoff).toBe(4.0);
    expect(useTestStore.getState().functionalLoading).toBe(false);
    expect(useTestStore.getState().functionalError).toBeNull();
  });

  it("treats a protein with no curated site and no ligand as a success", async () => {
    // Most uploads are exactly this. A red error where the honest answer is
    // "there is nothing here" is the failure P6 already fixed once.
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify(
              payload({ accession: null, accession_resolved: false, notes: ["none"] }),
            ),
            { status: 200 },
          ),
      ),
    );

    await useTestStore.getState().loadFunctional("abc");

    expect(useTestStore.getState().functional?.accession_resolved).toBe(false);
    expect(useTestStore.getState().functionalError).toBeNull();
  });

  it("records the status code on a transport failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Protein not found" }), { status: 404 }),
      ),
    );

    await useTestStore.getState().loadFunctional("abc");

    expect(useTestStore.getState().functionalError?.status).toBe(404);
    expect(useTestStore.getState().functional).toBeNull();
    expect(useTestStore.getState().functionalLoading).toBe(false);
  });

  it("drops a stale response so navigating A -> B never shows A's pockets", async () => {
    // A functional payload names residues by chain and ordinal. Showing
    // protein A's residue keys under protein B would select real residues of
    // the wrong molecule — the same class of error the mapping exists to stop.
    const { resolvers } = deferredFetch();

    const first = useTestStore.getState().loadFunctional("A");
    const second = useTestStore.getState().loadFunctional("B");

    resolvers[1](payload({ id: "B", accession: "B-ACC" }));
    await second;
    resolvers[0](payload({ id: "A", accession: "A-ACC" }));
    await first;

    expect(useTestStore.getState().functional?.accession).toBe("B-ACC");
  });

  it("clearProtein drops a payload that already landed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );
    await useTestStore.getState().loadFunctional("abc");
    expect(useTestStore.getState().functional).not.toBeNull();

    useTestStore.getState().clearProtein();

    expect(useTestStore.getState().functional).toBeNull();
    expect(useTestStore.getState().functionalError).toBeNull();
    expect(useTestStore.getState().functionalLoading).toBe(false);
  });

  it("clearProtein invalidates an in-flight load", async () => {
    const { resolvers } = deferredFetch();

    const inFlight = useTestStore.getState().loadFunctional("A");
    useTestStore.getState().clearProtein();
    resolvers[0](payload());
    await inFlight;

    expect(useTestStore.getState().functional).toBeNull();
  });

  it("loadProtein clears the previous protein's regions immediately", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );
    await useTestStore.getState().loadFunctional("A");
    expect(useTestStore.getState().functional).not.toBeNull();

    const { resolvers } = deferredFetch();
    const loading = useTestStore.getState().loadProtein("B");

    expect(useTestStore.getState().functional).toBeNull();

    resolvers[0](payload());
    await loading;
  });
});
