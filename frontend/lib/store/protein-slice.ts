import type { StateCreator } from "zustand";
import type {
  ProteinSummary,
  AnalyticsResponse,
  FunctionalRegions,
  ConfidenceResponse,
  ProteinAnnotations,
  ProteinComplexes,
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
  complexes: ProteinComplexes | null;
  complexesLoading: boolean;
  complexesError: ProteinLoadError | null;
  functional: FunctionalRegions | null;
  functionalLoading: boolean;
  functionalError: ProteinLoadError | null;
  confidence: ConfidenceResponse | null;
  confidenceLoading: boolean;
  confidenceError: ProteinLoadError | null;
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
  /**
   * Loads Complex Portal complexes from `GET /api/proteins/{id}/complexes`.
   *
   * Fourth independent request token, for the same reason the other three have
   * their own: the rail is mounted twice (side panel + stacked) and all four
   * requests race freely.
   *
   * A protein that belongs to no complex is a *successful* load carrying an
   * empty list, not an error — most proteins are in none. Only a transport or
   * 5xx failure lands in `complexesError`.
   */
  loadComplexes: (id: string) => Promise<void>;
  /**
   * Loads functional regions from `GET /api/proteins/{id}/functional-regions`.
   * Loads AlphaFold confidence analysis from
   * `GET /api/proteins/{id}/confidence` (A1).
   *
   * Fifth independent request token, for the same reason the other four have
   * their own: the rail is mounted twice and all five requests race freely.
   *
   * This endpoint degrades rather than failing — a UniProt outage still
   * returns the ligands and surface measured from the structure — so almost
   * nothing lands in `functionalError` except a transport failure.
   */
  loadFunctional: (id: string) => Promise<void>;
  /**
   * Loads AlphaFold confidence analysis from
   * `GET /api/proteins/{id}/confidence` (A1).
   *
   * An experimental structure is a *successful* load carrying
   * `has_plddt: false` and a prose note, not an error — pLDDT and PAE are
   * properties of a predicted model, and their absence is a fact about the
   * structure rather than a failure. Only a transport or 5xx failure lands in
   * `confidenceError`.
   */
  loadConfidence: (id: string) => Promise<void>;
  clearProtein: () => void;
}

// Module-level counters so stale responses can detect they were superseded.
let metaSeq = 0;
let analyticsSeq = 0;
let annotationsSeq = 0;
let complexesSeq = 0;
let functionalSeq = 0;
let confidenceSeq = 0;

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
  complexes: null,
  complexesLoading: false,
  complexesError: null,
  functional: null,
  functionalLoading: false,
  functionalError: null,
  confidence: null,
  confidenceLoading: false,
  confidenceError: null,
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
      complexes: null,
      complexesError: null,
      functional: null,
      functionalError: null,
      confidence: null,
      confidenceError: null,
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
  loadComplexes: async (id: string) => {
    const myReq = ++complexesSeq;
    set({ complexesLoading: true, complexesError: null });
    try {
      const c = await apiGet<ProteinComplexes>(`/api/proteins/${id}/complexes`);
      if (myReq !== complexesSeq) return;
      set({ complexes: c, complexesLoading: false });
    } catch (e) {
      if (myReq !== complexesSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ complexesError: { status, message }, complexesLoading: false });
    }
  },
  loadFunctional: async (id: string) => {
    const myReq = ++functionalSeq;
    set({ functionalLoading: true, functionalError: null });
    try {
      const f = await apiGet<FunctionalRegions>(
        `/api/proteins/${id}/functional-regions`,
      );
      if (myReq !== functionalSeq) return;
      set({ functional: f, functionalLoading: false });
    } catch (e) {
      if (myReq !== functionalSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ functionalError: { status, message }, functionalLoading: false });
    }
  },
  loadConfidence: async (id: string) => {
    const myReq = ++confidenceSeq;
    set({ confidenceLoading: true, confidenceError: null });
    try {
      const c = await apiGet<ConfidenceResponse>(
        `/api/proteins/${id}/confidence`,
      );
      if (myReq !== confidenceSeq) return;
      set({ confidence: c, confidenceLoading: false });
    } catch (e) {
      if (myReq !== confidenceSeq) return;
      const status = e instanceof ApiError ? e.status : null;
      const message = e instanceof Error ? e.message : String(e);
      set({ confidenceError: { status, message }, confidenceLoading: false });
    }
  },
  clearProtein: () => {
    // Bumping the sequences invalidates any in-flight loads.
    metaSeq++;
    analyticsSeq++;
    annotationsSeq++;
    complexesSeq++;
    functionalSeq++;
    confidenceSeq++;
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
      complexes: null,
      complexesError: null,
      complexesLoading: false,
      functional: null,
      functionalError: null,
      functionalLoading: false,
      confidence: null,
      confidenceError: null,
      confidenceLoading: false,
    });
  },
});
