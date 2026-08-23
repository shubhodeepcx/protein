import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { create } from "zustand";

import { createBlastSlice, type BlastSlice } from "@/lib/store/blast-slice";
import {
  nextPollDelay,
  recallJob,
  FAST_POLL_MS,
  SLOW_POLL_MS,
  SLOW_POLL_AFTER_SECONDS,
} from "@/lib/blast-job-memory";
import type { BlastJobStatus, BlastSubmitResponse } from "@/lib/types";

const JOB_ID = "ncbiblast-R20191128-094014-0332-71107816-p1m";
const PROTEIN = "abc123";

function makeStore() {
  return create<BlastSlice>()((...a) => createBlastSlice(...a));
}

function submitted(patch: Partial<BlastSubmitResponse> = {}): BlastSubmitResponse {
  return {
    job_id: JOB_ID,
    status: "QUEUED",
    program: "blastp",
    database: "uniprotkb",
    query_length: 605,
    query_source: "1CRN chain A",
    submitted_at: "2026-08-23T10:00:00Z",
    poll_url: `/api/blast/${JOB_ID}`,
    ...patch,
  };
}

function status(patch: Partial<BlastJobStatus> = {}): BlastJobStatus {
  return {
    job_id: JOB_ID,
    status: "RUNNING",
    finished: false,
    program: "blastp",
    database: "uniprotkb",
    query_length: 605,
    query_source: "1CRN chain A",
    submitted_at: "2026-08-23T10:00:00Z",
    elapsed_seconds: 4,
    poll_count: 1,
    message: "Running at EBI.",
    result: null,
    ...patch,
  };
}

/** Queue of responses, returned one per fetch call. */
function stubFetch(bodies: Array<{ status: number; body: unknown }>) {
  const calls: string[] = [];
  let i = 0;
  const mock = vi.fn(async (url: string) => {
    calls.push(url);
    const next = bodies[Math.min(i, bodies.length - 1)];
    i += 1;
    return new Response(JSON.stringify(next.body), { status: next.status });
  });
  vi.stubGlobal("fetch", mock);
  return { calls, mock };
}

describe("nextPollDelay", () => {
  it("polls fast while a job is young and eases off once it is clearly slow", () => {
    expect(nextPollDelay(0)).toBe(FAST_POLL_MS);
    expect(nextPollDelay(SLOW_POLL_AFTER_SECONDS - 1)).toBe(FAST_POLL_MS);
    expect(nextPollDelay(SLOW_POLL_AFTER_SECONDS)).toBe(SLOW_POLL_MS);
    expect(nextPollDelay(600)).toBe(SLOW_POLL_MS);
  });
});

describe("blastSlice", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
    useTestStore = makeStore();
  });

  afterEach(() => {
    useTestStore.getState().clearBlast();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("returns from submit as soon as the job id is back, with no results yet", async () => {
    stubFetch([{ status: 202, body: submitted() }]);

    await useTestStore.getState().submitBlast(PROTEIN, { protein_id: PROTEIN });

    const s = useTestStore.getState();
    expect(s.blastSubmitting).toBe(false);
    expect(s.blastJob?.job_id).toBe(JOB_ID);
    expect(s.blastJob?.finished).toBe(false);
    expect(s.blastJob?.result).toBeNull();
    expect(s.blastProteinId).toBe(PROTEIN);
  });

  it("remembers the job id so navigating away and back resumes it", async () => {
    stubFetch([{ status: 202, body: submitted() }]);

    await useTestStore.getState().submitBlast(PROTEIN, { protein_id: PROTEIN });

    expect(recallJob(PROTEIN)).toBe(JOB_ID);
  });

  it("keeps polling a running job and stops the moment it finishes", async () => {
    const { calls } = stubFetch([
      { status: 202, body: submitted() },
      { status: 200, body: status({ status: "RUNNING" }) },
      {
        status: 200,
        body: status({
          status: "FINISHED",
          finished: true,
          result: {
            program: "blastp",
            version: "BLASTP 2.9.0+",
            databases: ["uniprotkb_swissprot"],
            query_id: "ALS_HUMAN",
            query_definition: null,
            query_length: 605,
            hit_count: 1,
            hits: [],
            started_at: null,
            finished_at: null,
          },
        }),
      },
    ]);

    await useTestStore.getState().submitBlast(PROTEIN, { protein_id: PROTEIN });

    await vi.advanceTimersByTimeAsync(FAST_POLL_MS);
    expect(useTestStore.getState().blastJob?.status).toBe("RUNNING");

    await vi.advanceTimersByTimeAsync(FAST_POLL_MS);
    expect(useTestStore.getState().blastJob?.status).toBe("FINISHED");
    expect(useTestStore.getState().blastJob?.result?.hit_count).toBe(1);

    const afterFinish = calls.length;
    // The whole point: a finished job must not keep hitting the server.
    await vi.advanceTimersByTimeAsync(SLOW_POLL_MS * 6);
    expect(calls.length).toBe(afterFinish);
  });

  it("resumes an existing job by id without submitting a second search", async () => {
    const { calls } = stubFetch([{ status: 200, body: status() }]);

    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);

    expect(useTestStore.getState().blastJob?.job_id).toBe(JOB_ID);
    // A GET, never the POST that would start a duplicate job at EBI.
    expect(calls).toHaveLength(1);
    expect(calls[0]).toContain(`/api/blast/${JOB_ID}`);
  });

  it("does not restart polling for a job it is already watching", async () => {
    const { calls } = stubFetch([{ status: 200, body: status() }]);

    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);
    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);

    expect(calls).toHaveLength(1);
  });

  it("forgets a job the server no longer has, so polling cannot loop forever", async () => {
    stubFetch([{ status: 404, body: { detail: "no record of that BLAST job" } }]);
    window.localStorage.setItem(`proteolens.blast.${PROTEIN}`, JOB_ID);

    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);

    const s = useTestStore.getState();
    expect(s.blastJob).toBeNull();
    expect(s.blastError?.status).toBe(404);
    expect(recallJob(PROTEIN)).toBeNull();
  });

  it("keeps a still-running search alive through a transport blip", async () => {
    // A 502 from our own backend does not mean the search failed at EBI, so
    // dropping the job here would throw away work that is still in progress.
    const { calls } = stubFetch([
      { status: 502, body: { detail: "upstream hiccup" } },
      { status: 200, body: status() },
    ]);

    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);
    expect(useTestStore.getState().blastError).not.toBeNull();

    await vi.advanceTimersByTimeAsync(SLOW_POLL_MS);
    expect(calls.length).toBe(2);
    expect(useTestStore.getState().blastJob?.status).toBe("RUNNING");
    expect(useTestStore.getState().blastError).toBeNull();
  });

  it("records a submit failure without leaving the panel stuck submitting", async () => {
    stubFetch([{ status: 502, body: { detail: "Could not reach EBI" } }]);

    await useTestStore.getState().submitBlast(PROTEIN, { protein_id: PROTEIN });

    const s = useTestStore.getState();
    expect(s.blastSubmitting).toBe(false);
    expect(s.blastError?.status).toBe(502);
    expect(s.blastJob).toBeNull();
    expect(recallJob(PROTEIN)).toBeNull();
  });

  it("clearBlast stops polling and forgets the remembered id", async () => {
    const { calls } = stubFetch([{ status: 200, body: status() }]);
    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);
    window.localStorage.setItem(`proteolens.blast.${PROTEIN}`, JOB_ID);
    const before = calls.length;

    useTestStore.getState().clearBlast(PROTEIN);

    await vi.advanceTimersByTimeAsync(SLOW_POLL_MS * 4);
    expect(calls.length).toBe(before);
    expect(useTestStore.getState().blastJob).toBeNull();
    expect(recallJob(PROTEIN)).toBeNull();
  });

  it("a superseded poll loop cannot overwrite the newer job", async () => {
    stubFetch([{ status: 200, body: status() }]);
    await useTestStore.getState().resumeBlast(PROTEIN, JOB_ID);

    stubFetch([{ status: 200, body: status({ job_id: "ncbiblast-second" }) }]);
    await useTestStore.getState().resumeBlast("other-protein", "ncbiblast-second");

    await vi.advanceTimersByTimeAsync(SLOW_POLL_MS * 3);
    expect(useTestStore.getState().blastJob?.job_id).toBe("ncbiblast-second");
    expect(useTestStore.getState().blastProteinId).toBe("other-protein");
  });
});

describe("blastSlice.loadSimilar", () => {
  let useTestStore: ReturnType<typeof makeStore>;

  beforeEach(() => {
    useTestStore = makeStore();
  });

  afterEach(() => vi.unstubAllGlobals());

  it("loads UniRef homologs for a protein", async () => {
    stubFetch([
      {
        status: 200,
        body: {
          id: PROTEIN,
          accession: "P01308",
          accession_resolved: true,
          resolution_note: "note",
          identity_threshold: 0.5,
          cluster_id: "UniRef50_P01308",
          cluster_name: "Cluster: Insulin",
          member_count: 35,
          organism_count: 20,
          members: [],
          truncated: true,
        },
      },
    ]);

    await useTestStore.getState().loadSimilar(PROTEIN);

    expect(useTestStore.getState().similar?.cluster_id).toBe("UniRef50_P01308");
    expect(useTestStore.getState().similarLoading).toBe(false);
  });

  it("records a failure without clearing the loading flag", async () => {
    stubFetch([{ status: 502, body: { detail: "Could not reach UniProt" } }]);

    await useTestStore.getState().loadSimilar(PROTEIN);

    const s = useTestStore.getState();
    expect(s.similarLoading).toBe(false);
    expect(s.similarError?.status).toBe(502);
  });
});
