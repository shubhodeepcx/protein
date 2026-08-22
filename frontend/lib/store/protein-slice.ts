import type { StateCreator } from "zustand";
import type {
  ProteinSummary,
  AnalyticsResponse,
  ProteinAnnotations,
} from "@/lib/types";
import { apiGet, ApiError } from "@/lib/api";

export interface ProteinLoadError {
  status: number | null;
  message: string;
}

export interface ProteinSlice {
  current: ProteinSummary | null;
  isLoading: boolean;
  error: ProteinLoadError | null;
  analytics: AnalyticsResponse | null;
  analyticsLoading: boolean;
  analyticsError: ProteinLoadError | null;
  annotations: ProteinAnnotations | null;
  annotationsLoading: boolean;
  annotationsError: ProteinLoadError | null;
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
  /**
   * Loads analytics for a protein from `GET /api/proteins/{id}/analytics`.
   *
   * Uses its own monotonic request token (independent of `loadProtein`) so
   * the two requests can race without clobbering each other.
   */
  loadAnalytics: (id: string) => Promise<void>;
  /**
   * Loads UniProt annotations from `GET /api/proteins/{id}/annotations`.
   *
   * Third independent request token, for the same reason the other two have
   * their own: the rail is mounted twice (side panel + stacked) and the three
   * requests race freely.
   *
   * A protein with no resolvable accession is a *successful* load carrying an
   * empty payload, not an error — the panel says why it is empty. Only a
   * transport or 5xx failure lands in `annotationsError`.
   */
  loadAnnotations: (id: string) => Promise<void>;
  clearProtein: () => void;
}

// Module-level counters so stale responses can detect they were superseded.
let metaSeq = 0;
let analyticsSeq = 0;
let annotationsSeq = 0;

export const createProteinSlice: StateCreator<ProteinSlice, [], [], ProteinSlice> = (
  set,
) => ({
  current: null,
  isLoading: false,
  error: null,
  analytics: null,
  analyticsLoading: false,
  analyticsError: null,
  annotations: null,
  annotationsLoading: false,
  annotationsError: null,
  loadProtein: async (id: string) => {
    const myReq = ++metaSeq;
    // Clear stale data immediately so consumers don't see protein A while loading B.
    // Also clear analytics for the previous protein so we never render mismatched data.
    set({
      current: null,
      isLoading: true,
      error: null,
      analytics: null,
      analyticsError: null,
      annotations: null,
      annotationsError: null,
    });
    try {
      const summary = await apiGet<ProteinSummary>(`/api/proteins/${id}`);
      if (myReq !== metaSeq) return; // a newer load started; drop this result
      set({ current: summary, isLoading: false });
    } catch (e) {
      if (myReq !== metaSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ error: { status, message }, isLoading: false });
    }
  },
  loadAnalytics: async (id: string) => {
    const myReq = ++analyticsSeq;
    set({ analyticsLoading: true, analyticsError: null });
    try {
      const a = await apiGet<AnalyticsResponse>(`/api/proteins/${id}/analytics`);
      if (myReq !== analyticsSeq) return;
      set({ analytics: a, analyticsLoading: false });
    } catch (e) {
      if (myReq !== analyticsSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ analyticsError: { status, message }, analyticsLoading: false });
    }
  },
  loadAnnotations: async (id: string) => {
    const myReq = ++annotationsSeq;
    set({ annotationsLoading: true, annotationsError: null });
    try {
      const a = await apiGet<ProteinAnnotations>(
        `/api/proteins/${id}/annotations`,
      );
      if (myReq !== annotationsSeq) return;
      set({ annotations: a, annotationsLoading: false });
    } catch (e) {
      if (myReq !== annotationsSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ annotationsError: { status, message }, annotationsLoading: false });
    }
  },
  clearProtein: () => {
    // Bumping the sequences invalidates any in-flight loads.
    metaSeq++;
    analyticsSeq++;
    annotationsSeq++;
    set({
      current: null,
      error: null,
      isLoading: false,
      analytics: null,
      analyticsError: null,
      analyticsLoading: false,
      annotations: null,
      annotationsError: null,
      annotationsLoading: false,
    });
  },
});
