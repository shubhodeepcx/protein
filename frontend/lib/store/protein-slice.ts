import type { StateCreator } from "zustand";
import type { ProteinSummary } from "@/lib/types";
import { apiGet } from "@/lib/api";

export interface ProteinSlice {
  current: ProteinSummary | null;
  isLoading: boolean;
  error: string | null;
  /**
   * Loads protein metadata by id from `GET /api/proteins/{id}`.
   *
   * Errors are stored on the slice as a string; ApiError messages already
   * include status + detail when available (see `lib/api.ts`).
   */
  loadProtein: (id: string) => Promise<void>;
  clearProtein: () => void;
}

export const createProteinSlice: StateCreator<ProteinSlice, [], [], ProteinSlice> = (
  set,
) => ({
  current: null,
  isLoading: false,
  error: null,
  loadProtein: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const summary = await apiGet<ProteinSummary>(`/api/proteins/${id}`);
      set({ current: summary, isLoading: false });
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : String(e),
        isLoading: false,
        current: null,
      });
    }
  },
  clearProtein: () => set({ current: null, error: null }),
});
