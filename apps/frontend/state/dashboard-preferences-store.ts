import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { DashboardModeValue } from "@/features/dashboard/lib/widget-registry";

interface DashboardPreferencesState {
  /** The mode shown before any `?mode=` URL param overrides it — the
   * URL always wins once present (§51: URL state stays shareable/safe),
   * this is only the default for a fresh visit. */
  preferredMode: DashboardModeValue;
  setPreferredMode: (mode: DashboardModeValue) => void;
  hiddenWidgetIds: string[];
  toggleWidget: (id: string) => void;
}

/**
 * §24: local-only dashboard personalization. Never synced to a
 * backend — no such preference route exists on this backend (confirmed
 * absent, see `docs/frontend/backend-v1-integration-limitations.md`),
 * matching the exact `localStorage`-only precedent
 * `useTableDensityStore`/`useRecentSearchesStore` already established.
 * "Density" (§24's third example) is deliberately not modeled here: it
 * only ever meant *table row* density (`useTableDensityStore`), and a
 * card-grid dashboard has no equivalent concept to reuse it for — see
 * the developer guide.
 */
export const useDashboardPreferencesStore = create<DashboardPreferencesState>()(
  persist(
    (set) => ({
      preferredMode: "executive",
      setPreferredMode: (mode) => set({ preferredMode: mode }),
      hiddenWidgetIds: [],
      toggleWidget: (id) =>
        set((state) => ({
          hiddenWidgetIds: state.hiddenWidgetIds.includes(id)
            ? state.hiddenWidgetIds.filter((existing) => existing !== id)
            : [...state.hiddenWidgetIds, id],
        })),
    }),
    { name: "aiios-dashboard-preferences", storage: createJSONStorage(() => localStorage) },
  ),
);
