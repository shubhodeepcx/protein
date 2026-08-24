import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { create } from "zustand";

import { createProteinSlice, type ProteinSlice } from "@/lib/store/protein-slice";
import type { ConfidenceResponse } from "@/lib/types";

function makeStore() {
  return create<ProteinSlice>()((...a) => createProteinSlice(...a));
}

function payload(patch: Partial<ConfidenceResponse> = {}): ConfidenceResponse {
  return {
    id: "id",
    has_plddt: true,
    note: "",
    accession: "P01308",
    residue_count: 110,
    mean_plddt: 52.91,
    bands: [],
    low_confidence_regions: [],
    low_confidence_residue_count: 96,
    low_confidence_fraction: 96 / 110,
    low_confidence_threshold: 70,
    pae: {
      available: true,
      unavailable_reason: "",
      residue_count: 110,
      size: 110,
      bin_size: 1,
      downsampled: false,
      max_cells: 16384,
      aggregation: "none",
      max_error: 31.75,
      resolution_label: "Full resolution.",
      values: [],
      source_url: "",
    },
    warnings: [],
    ...patch,
  };
}

function deferredFetch() {
  const resolvers: ((body: ConfidenceResponse) => void)[] = [];
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

describe("proteinSlice.loadConfidence", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("requests the confidence endpoint for the given id", async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        urls.push(String(input));
        return new Response(JSON.stringify(payload()), { status: 200 });
      }),
    );

    await useTestStore.getState().loadConfidence("abc");

    expect(urls[0]).toContain("/api/proteins/abc/confidence");
  });

  it("stores the payload and clears the loading flag", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );

    await useTestStore.getState().loadConfidence("abc");

    expect(useTestStore.getState().confidence?.mean_plddt).toBe(52.91);
    expect(useTestStore.getState().confidenceLoading).toBe(false);
    expect(useTestStore.getState().confidenceError).toBeNull();
  });

  it("treats an experimental structure as a success, not an error", async () => {
    // pLDDT and PAE are properties of a predicted model. Their absence is a
    // fact about the structure, and putting a red error there would tell the
    // user something is broken when nothing is.
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify(
              payload({
                has_plddt: false,
                note: "This is an experimental structure.",
                mean_plddt: null,
              }),
            ),
            { status: 200 },
          ),
      ),
    );

    await useTestStore.getState().loadConfidence("abc");

    expect(useTestStore.getState().confidence?.has_plddt).toBe(false);
    expect(useTestStore.getState().confidenceError).toBeNull();
  });

  it("records the status code on a failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Protein not found" }), {
            status: 404,
          }),
      ),
    );

    await useTestStore.getState().loadConfidence("abc");

    expect(useTestStore.getState().confidenceError?.status).toBe(404);
    expect(useTestStore.getState().confidence).toBeNull();
    expect(useTestStore.getState().confidenceLoading).toBe(false);
  });

  it("drops a stale response so navigating A -> B never shows A's confidence", async () => {
    const { resolvers } = deferredFetch();

    const first = useTestStore.getState().loadConfidence("A");
    const second = useTestStore.getState().loadConfidence("B");

    resolvers[1](payload({ id: "B", accession: "B-ACC" }));
    await second;
    resolvers[0](payload({ id: "A", accession: "A-ACC" }));
    await first;

    expect(useTestStore.getState().confidence?.accession).toBe("B-ACC");
  });

  it("uses a token independent of the other loaders", async () => {
    // The rail is mounted twice and all five requests race freely. Sharing a
    // counter would let an annotations response cancel a confidence one.
    const { resolvers } = deferredFetch();

    const confidence = useTestStore.getState().loadConfidence("A");
    const annotations = useTestStore.getState().loadAnnotations("A");

    resolvers[1]({} as ConfidenceResponse);
    await annotations;
    resolvers[0](payload({ accession: "STILL-MINE" }));
    await confidence;

    expect(useTestStore.getState().confidence?.accession).toBe("STILL-MINE");
  });

  it("clearProtein drops a payload that already landed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );
    await useTestStore.getState().loadConfidence("abc");
    expect(useTestStore.getState().confidence).not.toBeNull();

    useTestStore.getState().clearProtein();

    expect(useTestStore.getState().confidence).toBeNull();
    expect(useTestStore.getState().confidenceError).toBeNull();
    expect(useTestStore.getState().confidenceLoading).toBe(false);
  });

  it("clearProtein invalidates an in-flight load", async () => {
    const { resolvers } = deferredFetch();

    const inFlight = useTestStore.getState().loadConfidence("A");
    useTestStore.getState().clearProtein();
    resolvers[0](payload());
    await inFlight;

    expect(useTestStore.getState().confidence).toBeNull();
  });

  it("loadProtein clears the previous protein's confidence immediately", async () => {
    // Otherwise the panel shows protein A's disordered tail under protein B's
    // name for as long as the second request takes — and a confidence claim
    // about the wrong protein is worse than no claim.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );
    await useTestStore.getState().loadConfidence("A");
    expect(useTestStore.getState().confidence).not.toBeNull();

    const { resolvers } = deferredFetch();
    const loading = useTestStore.getState().loadProtein("B");

    expect(useTestStore.getState().confidence).toBeNull();

    resolvers[0](payload());
    await loading;
  });
});
