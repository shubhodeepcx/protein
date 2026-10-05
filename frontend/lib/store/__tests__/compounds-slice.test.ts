import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { create } from "zustand";

import { createProteinSlice, type ProteinSlice } from "@/lib/store/protein-slice";
import type { CompoundsResponse } from "@/lib/types";

function makeStore() {
  return create<ProteinSlice>()((...a) => createProteinSlice(...a));
}

function payload(id: string): CompoundsResponse {
  return {
    protein_id: id,
    contact_cutoff: 4,
    nucleic_acids: [],
    groups: [],
    water_count: 0,
    notes: [],
  };
}

function deferredFetch() {
  const resolvers: ((response: Response) => void)[] = [];
  const fetchMock = vi.fn(
    (_input: RequestInfo | URL) =>
      new Promise<Response>((resolve) => resolvers.push(resolve)),
  );
  vi.stubGlobal("fetch", fetchMock);
  return { resolvers, fetchMock };
}

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

describe("proteinSlice.loadCompounds", () => {
  let useTestStore: ReturnType<typeof makeStore>;
  beforeEach(() => {
    useTestStore = makeStore();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("fetches /compounds and stores the payload", async () => {
    const { resolvers, fetchMock } = deferredFetch();
    const pending = useTestStore.getState().loadCompounds("abc");
    expect(useTestStore.getState().compoundsLoading).toBe(true);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/proteins/abc/compounds");
    resolvers[0](ok(payload("abc")));
    await pending;
    expect(useTestStore.getState().compounds?.protein_id).toBe("abc");
    expect(useTestStore.getState().compoundsLoading).toBe(false);
  });

  it("drops a response that a newer load superseded", async () => {
    const { resolvers } = deferredFetch();
    const first = useTestStore.getState().loadCompounds("old");
    const second = useTestStore.getState().loadCompounds("new");
    resolvers[1](ok(payload("new")));
    await second;
    resolvers[0](ok(payload("old")));
    await first;
    expect(useTestStore.getState().compounds?.protein_id).toBe("new");
  });

  it("records a failure in compoundsError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "nope" }), { status: 500 })),
    );
    await useTestStore.getState().loadCompounds("abc");
    expect(useTestStore.getState().compounds).toBeNull();
    expect(useTestStore.getState().compoundsError?.status).toBe(500);
  });

  it("is cleared with the protein", () => {
    useTestStore.setState({ compounds: payload("abc") });
    useTestStore.getState().clearProtein();
    expect(useTestStore.getState().compounds).toBeNull();
  });
});
