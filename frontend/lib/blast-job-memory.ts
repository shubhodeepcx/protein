/**
 * Remembering a running BLAST job across navigation (P8).
 *
 * A search takes 30 s to several minutes, which is long enough for the user to
 * go and look at something else. The job id is the only thing the browser needs
 * to hold: the server keeps the job, so coming back means resuming rather than
 * starting a second search at EBI.
 *
 * Kept out of the store slice because none of it is state — it is one key per
 * protein in `localStorage`, plus the schedule the poll loop follows.
 */

/** Poll fast while a job is young, then ease off. Jobs run for minutes. */
export const FAST_POLL_MS = 2000;
export const SLOW_POLL_MS = 5000;
/** After this many seconds the job is clearly not a quick one. */
export const SLOW_POLL_AFTER_SECONDS = 30;

const STORAGE_PREFIX = "proteolens.blast.";

function storageKey(proteinId: string): string {
  return `${STORAGE_PREFIX}${proteinId}`;
}

/**
 * Store (or, with `null`, forget) the job id for one protein.
 *
 * `localStorage` is absent during SSR and throws outright in some private
 * browsing modes, so every access is guarded: a remembered job id is a
 * convenience, never a correctness requirement.
 */
export function rememberJob(proteinId: string, jobId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (jobId === null) window.localStorage.removeItem(storageKey(proteinId));
    else window.localStorage.setItem(storageKey(proteinId), jobId);
  } catch {
    // Ignored on purpose — see the doc comment above.
  }
}

/** The job id remembered for this protein, or null. */
export function recallJob(proteinId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(storageKey(proteinId));
  } catch {
    return null;
  }
}

/** How long to wait before the next poll, given how long the job has run. */
export function nextPollDelay(elapsedSeconds: number): number {
  return elapsedSeconds >= SLOW_POLL_AFTER_SECONDS ? SLOW_POLL_MS : FAST_POLL_MS;
}
