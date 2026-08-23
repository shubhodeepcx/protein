import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { create } from "zustand";

import { createProteinSlice, type ProteinSlice } from "@/lib/store/protein-slice";
import type { ProteinComplexes } from "@/lib/types";

function makeStore() {
  return create<ProteinSlice>()((...a) => createProteinSlice(...a));
}

function payload(patch: Partial<ProteinComplexes> = {}): ProteinComplexes {
  return {
    id: "id",
    accession: "P69905",
    accession_resolved: true,
    resolution_note: "note",
    query: "P69905",
    complexes: [
      {
        accession: "CPX-2158",
        name: "Hemoglobin HbA complex",
        organism: "Homo sapiens",
        description: "Binds oxygen.",
        predicted: false,
        url: "https://www.ebi.ac.uk/complexportal/complex/CPX-2158",
        participants: [],
      },
    ],
    search_matches: 1,
    ...patch,
  };
}

/** One deferred fetch response per call, resolved by the test. */
function deferredFetch() {
  const resolvers: ((body: ProteinComplexes) => void)[] = [];
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

describe("proteinSlice.loadComplexes", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("requests the complexes endpoint for the given id", async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        urls.push(String(input));
        return new Response(JSON.stringify(payload()), { status: 200 });
      }),
    );

    await useTestStore.getState().loadComplexes("abc");

    expect(urls[0]).toContain("/api/proteins/abc/complexes");
  });

  it("stores the payload and clears the loading flag", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );

    await useTestStore.getState().loadComplexes("abc");

    expect(useTestStore.getState().complexes?.complexes[0].accession).toBe("CPX-2158");
    expect(useTestStore.getState().complexesLoading).toBe(false);
    expect(useTestStore.getState().complexesError).toBeNull();
  });

  it("treats a protein in no complex as a success, not an error", async () => {
    // Most proteins are in none. Reporting that as a failure would put a red
    // error where the honest answer is "there is nothing here".
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify(payload({ complexes: [], search_matches: 0 })),
            { status: 200 },
          ),
      ),
    );

    await useTestStore.getState().loadComplexes("abc");

    expect(useTestStore.getState().complexes?.complexes).toEqual([]);
    expect(useTestStore.getState().complexesError).toBeNull();
  });

  it("records the status code on a failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Could not reach the portal." }), {
            status: 502,
          }),
      ),
    );

    await useTestStore.getState().loadComplexes("abc");

    expect(useTestStore.getState().complexesError?.status).toBe(502);
    expect(useTestStore.getState().complexes).toBeNull();
    expect(useTestStore.getState().complexesLoading).toBe(false);
  });

  it("drops a stale response so navigating A -> B never shows A's complexes", async () => {
    const { resolvers } = deferredFetch();

    const first = useTestStore.getState().loadComplexes("A");
    const second = useTestStore.getState().loadComplexes("B");

    resolvers[1](payload({ id: "B", accession: "B-ACC" }));
    await second;
    resolvers[0](payload({ id: "A", accession: "A-ACC" }));
    await first;

    expect(useTestStore.getState().complexes?.accession).toBe("B-ACC");
  });

  it("clearProtein drops a payload that already landed", async () => {
    // Invalidating in-flight requests is not enough: leaving the last
    // protein's complexes in the store shows them under the next protein.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );
    await useTestStore.getState().loadComplexes("abc");
    expect(useTestStore.getState().complexes).not.toBeNull();

    useTestStore.getState().clearProtein();

    expect(useTestStore.getState().complexes).toBeNull();
    expect(useTestStore.getState().complexesError).toBeNull();
    expect(useTestStore.getState().complexesLoading).toBe(false);
  });

  it("clearProtein invalidates an in-flight load", async () => {
    const { resolvers } = deferredFetch();

    const inFlight = useTestStore.getState().loadComplexes("A");
    useTestStore.getState().clearProtein();
    resolvers[0](payload());
    await inFlight;

    expect(useTestStore.getState().complexes).toBeNull();
  });

  it("loadProtein clears the previous protein's complexes immediately", async () => {
    // Otherwise the rail shows protein A's complexes under protein B's name
    // for as long as the second request takes.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload()), { status: 200 })),
    );
    await useTestStore.getState().loadComplexes("A");
    expect(useTestStore.getState().complexes).not.toBeNull();

    const { resolvers } = deferredFetch();
    const loading = useTestStore.getState().loadProtein("B");

    expect(useTestStore.getState().complexes).toBeNull();

    resolvers[0](payload());
    await loading;
  });
});
