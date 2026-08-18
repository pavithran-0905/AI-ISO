import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type TableDensity = "comfortable" | "compact";

interface TableDensityState {
  density: TableDensity;
  setDensity: (density: TableDensity) => void;
}

/**
 * A shared, persisted density preference for any data-dense table in
 * the app (docs/frontend Prompt 006 §16: "persist preference only
 * through the existing frontend client-state architecture") — not
 * scoped to Monitoring specifically, since every future large table
 * (Alerting, Automation, ...) will want the same toggle.
 */
export const useTableDensityStore = create<TableDensityState>()(
  persist(
    (set) => ({
      density: "comfortable",
      setDensity: (density) => set({ density }),
    }),
    { name: "aiios-table-density", storage: createJSONStorage(() => localStorage) },
  ),
);
