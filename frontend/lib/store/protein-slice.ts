import type { StateCreator } from "zustand";
import type { ProteinSummary } from "@/lib/types";
import { apiGet, ApiError } from "@/lib/api";

export interface ProteinLoadError {
  status: number | null;
  message: string;
}

export interface ProteinSlice {
  current: ProteinSummary | null;
  isLoading: boolean;
  error: ProteinLoadError | null;
  /**
   * Loads protein metadata by id from `GET /api/proteins/{id}`.
   *
   * Errors are stored on the slice as `{ status, message }` so consumers can
   * branch on the HTTP code (e.g. classify 404 → not found) rather than
   * string-matching the message. `ApiError.status` is surfaced when the
   * underlying fetch failed with a typed API error; for non-`ApiError`
   * failures (network, parse), `status` is `null`.
   *
   * Concurrent calls are guarded by a monotonic request token — stale
   * responses whose token no longer matches the latest sequence are dropped
   * so rapid navigation between `/viewer/A` and `/viewer/B` never lets the
   * older request overwrite the newer one.
   */
  loadProtein: (id: string) => Promise<void>;
  clearProtein: () => void;
}

// Module-level counter so stale responses can detect they were superseded.
let requestSeq = 0;

export const createProteinSlice: StateCreator<ProteinSlice, [], [], ProteinSlice> = (
  set,
) => ({
  current: null,
  isLoading: false,
  error: null,
  loadProtein: async (id: string) => {
    const myReq = ++requestSeq;
    // Clear stale data immediately so consumers don't see protein A while loading B.
    set({ current: null, isLoading: true, error: null });
    try {
      const summary = await apiGet<ProteinSummary>(`/api/proteins/${id}`);
      if (myReq !== requestSeq) return; // a newer load started; drop this result
      set({ current: summary, isLoading: false });
    } catch (e) {
      if (myReq !== requestSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ error: { status, message }, isLoading: false });
    }
  },
  clearProtein: () => {
    // Bumping the sequence invalidates any in-flight loadProtein.
    requestSeq++;
    set({ current: null, error: null, isLoading: false });
  },
});
