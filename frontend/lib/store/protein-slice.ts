import type { StateCreator } from "zustand";
import type { ProteinSummary } from "@/lib/types";

export interface ProteinSlice {
  current: ProteinSummary | null;
  isLoading: boolean;
  error: string | null;
  /**
   * Loads protein metadata by id.
   *
   * P0 stub: assigns a placeholder ProteinSummary so the rest of the UI can
   * be wired up. P2 replaces this with `apiGet<ProteinSummary>(...)`.
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
    // P0 stub: pretend we fetched a summary. Real call comes in P2.
    const placeholder: ProteinSummary = {
      id,
      source: "uploaded",
      source_id: null,
      name: null,
      organism: null,
      file_url: `/api/proteins/${id}/file`,
      file_format: "pdb",
      chains: [],
      residue_count: 0,
      atom_count: 0,
      molecular_weight: 0,
      has_plddt: false,
      warnings: [],
    };
    set({ current: placeholder, isLoading: false });
  },
  clearProtein: () => set({ current: null, error: null }),
});
