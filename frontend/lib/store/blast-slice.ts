import type { StateCreator } from "zustand";
import type {
  BlastJobStatus,
  BlastSubmitRequest,
  BlastSubmitResponse,
  SimilarProteinsResponse,
} from "@/lib/types";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import {
  FAST_POLL_MS,
  SLOW_POLL_MS,
  nextPollDelay,
  rememberJob,
} from "@/lib/blast-job-memory";
import type { ProteinLoadError } from "./protein-slice";

/**
 * P8 — the only asynchronous flow in the app.
 *
 * A BLAST search takes 30 s to several minutes, so the slice owns a polling
 * loop rather than a single request. Three things follow from that, and each
 * is the reason for a piece of state here:
 *
 * * **The wait must not look hung.** `job.elapsed_seconds` and `job.message`
 *   come from the server on every poll, so the panel shows how long the search
 *   has really been running instead of an indeterminate spinner.
 * * **It must survive navigation.** The job id is written to `localStorage`
 *   keyed by protein, so leaving the viewer and coming back — or reloading the
 *   page outright — resumes the same job instead of starting a second one.
 * * **It must stop.** Polling ends the moment the server says `finished`, and
 *   a stale loop is cancelled by a token bump exactly like the other slices'
 *   in-flight requests.
 */

export interface BlastSlice {
  /** The job being watched, or null when none has been started for this protein. */
  blastJob: BlastJobStatus | null;
  /** Which protein `blastJob` belongs to — a job must never leak across viewers. */
  blastProteinId: string | null;
  blastSubmitting: boolean;
  blastError: ProteinLoadError | null;

  /** Submits a search and starts polling. Resolves as soon as the id is back. */
  submitBlast: (proteinId: string, request: BlastSubmitRequest) => Promise<void>;
  /**
   * Picks a job back up by id — used on mount when `localStorage` remembers
   * one, so navigating away and back does not lose the search.
   */
  resumeBlast: (proteinId: string, jobId: string) => Promise<void>;
  /** Forgets the job and stops polling. */
  clearBlast: (proteinId?: string) => void;

  similar: SimilarProteinsResponse | null;
  similarLoading: boolean;
  similarError: ProteinLoadError | null;
  loadSimilar: (id: string) => Promise<void>;
}

// Module-level so a superseded poll loop can detect it was replaced, mirroring
// the request tokens in `protein-slice`.
let pollSeq = 0;
let similarSeq = 0;
let pollTimer: ReturnType<typeof setTimeout> | null = null;

function cancelTimer(): void {
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function toLoadError(e: unknown): ProteinLoadError {
  return {
    status: e instanceof ApiError ? e.status : null,
    message: e instanceof Error ? e.message : String(e),
  };
}

export const createBlastSlice: StateCreator<BlastSlice, [], [], BlastSlice> = (
  set,
  get,
) => {
  async function pollOnce(proteinId: string, jobId: string, token: number) {
    if (token !== pollSeq) return;
    try {
      const job = await apiGet<BlastJobStatus>(`/api/blast/${jobId}`);
      if (token !== pollSeq) return;
      set({ blastJob: job, blastProteinId: proteinId, blastError: null });
      if (job.finished) {
        // A finished job stays remembered: coming back to the viewer should
        // show the results again, not an empty form.
        cancelTimer();
        return;
      }
      cancelTimer();
      pollTimer = setTimeout(
        () => void pollOnce(proteinId, jobId, token),
        nextPollDelay(job.elapsed_seconds),
      );
    } catch (e) {
      if (token !== pollSeq) return;
      const error = toLoadError(e);
      if (error.status === 404) {
        // The server forgot the job (restart, or it aged out). Keeping the id
        // would make every future poll fail; drop it and let the user re-run.
        cancelTimer();
        rememberJob(proteinId, null);
        set({ blastJob: null, blastError: error });
        return;
      }
      // A transport blip must not kill a search that is still running upstream.
      set({ blastError: error });
      cancelTimer();
      pollTimer = setTimeout(() => void pollOnce(proteinId, jobId, token), SLOW_POLL_MS);
    }
  }

  return {
    blastJob: null,
    blastProteinId: null,
    blastSubmitting: false,
    blastError: null,
    similar: null,
    similarLoading: false,
    similarError: null,

    submitBlast: async (proteinId: string, request: BlastSubmitRequest) => {
      const token = ++pollSeq;
      cancelTimer();
      set({
        blastSubmitting: true,
        blastError: null,
        blastJob: null,
        blastProteinId: proteinId,
      });
      try {
        const submitted = await apiPost<BlastSubmitResponse>("/api/blast", request);
        if (token !== pollSeq) return;
        rememberJob(proteinId, submitted.job_id);
        set({
          blastSubmitting: false,
          blastJob: {
            ...submitted,
            finished: false,
            elapsed_seconds: 0,
            poll_count: 0,
            message: "Submitted. Waiting for EBI to pick the job up.",
            result: null,
          },
        });
        pollTimer = setTimeout(
          () => void pollOnce(proteinId, submitted.job_id, token),
          FAST_POLL_MS,
        );
      } catch (e) {
        if (token !== pollSeq) return;
        set({ blastSubmitting: false, blastError: toLoadError(e) });
      }
    },

    resumeBlast: async (proteinId: string, jobId: string) => {
      const current = get();
      if (current.blastJob?.job_id === jobId && current.blastProteinId === proteinId) {
        return; // already watching this one
      }
      const token = ++pollSeq;
      cancelTimer();
      set({ blastError: null, blastProteinId: proteinId });
      await pollOnce(proteinId, jobId, token);
    },

    clearBlast: (proteinId?: string) => {
      pollSeq++; // invalidate any in-flight poll
      cancelTimer();
      const target = proteinId ?? get().blastProteinId;
      if (target) rememberJob(target, null);
      set({
        blastJob: null,
        blastProteinId: null,
        blastSubmitting: false,
        blastError: null,
      });
    },

    loadSimilar: async (id: string) => {
      const token = ++similarSeq;
      set({ similarLoading: true, similarError: null });
      try {
        const data = await apiGet<SimilarProteinsResponse>(
          `/api/proteins/${id}/similar`,
        );
        if (token !== similarSeq) return;
        set({ similar: data, similarLoading: false });
      } catch (e) {
        if (token !== similarSeq) return;
        set({ similarError: toLoadError(e), similarLoading: false });
      }
    },
  };
};
