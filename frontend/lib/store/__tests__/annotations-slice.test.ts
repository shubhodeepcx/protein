import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { create } from "zustand";

import { createProteinSlice, type ProteinSlice } from "@/lib/store/protein-slice";
import type { ProteinAnnotations } from "@/lib/types";

function makeStore() {
  return create<ProteinSlice>()((...a) => createProteinSlice(...a));
}

function payload(patch: Partial<ProteinAnnotations> = {}): ProteinAnnotations {
  return {
    id: "id",
    accession: "P01308",
    accession_resolved: true,
    resolution_note: "note",
    entry_name: "INS_HUMAN",
    protein_name: "Insulin",
    gene_names: [],
    organism: null,
    taxon_id: null,
    lineage: [],
    function: [],
    catalytic_activity: [],
    gene_ontology: {
      biological_process: [],
      cellular_component: [],
      molecular_function: [],
    },
    keywords: [],
    subcellular_locations: [],
    subcellular_location_notes: [],
    transmembrane: [],
    diseases: [],
    ptm: [],
    ptm_features: [],
    cross_references: [],
    ...patch,
  };
}

/** One deferred fetch response per call, resolved by the test. */
function deferredFetch() {
  const resolvers: ((body: ProteinAnnotations) => void)[] = [];
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

describe("proteinSlice.loadAnnotations", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("stores the payload and clears the loading flag", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );

    await useTestStore.getState().loadAnnotations("abc");

    expect(useTestStore.getState().annotations?.protein_name).toBe("Insulin");
    expect(useTestStore.getState().annotationsLoading).toBe(false);
    expect(useTestStore.getState().annotationsError).toBeNull();
  });

  it("records the status code on a failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Could not reach UniProt." }), {
            status: 502,
          }),
      ),
    );

    await useTestStore.getState().loadAnnotations("abc");

    expect(useTestStore.getState().annotationsError?.status).toBe(502);
    expect(useTestStore.getState().annotations).toBeNull();
    expect(useTestStore.getState().annotationsLoading).toBe(false);
  });

  it("drops a stale response so navigating A -> B never shows A's annotations", async () => {
    // The rail is mounted twice and the user can navigate mid-flight; without
    // the request token the slower first response overwrites the newer one.
    const { resolvers } = deferredFetch();

    const first = useTestStore.getState().loadAnnotations("A");
    const second = useTestStore.getState().loadAnnotations("B");

    resolvers[1](payload({ id: "B", protein_name: "Protein B" }));
    await second;
    resolvers[0](payload({ id: "A", protein_name: "Protein A" }));
    await first;

    expect(useTestStore.getState().annotations?.protein_name).toBe("Protein B");
  });

  it("clearProtein invalidates an in-flight load", async () => {
    const { resolvers } = deferredFetch();

    const inFlight = useTestStore.getState().loadAnnotations("A");
    useTestStore.getState().clearProtein();
    resolvers[0](payload());
    await inFlight;

    expect(useTestStore.getState().annotations).toBeNull();
  });
});
