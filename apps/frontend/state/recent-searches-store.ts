import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

const MAX_RECENT_SEARCHES = 5;

interface RecentSearchesState {
  terms: string[];
  addSearch: (term: string) => void;
  clear: () => void;
}

/**
 * §21: a small, bounded, purely local history of recent search terms
 * — never sent to the backend (no route accepts one), plain text only
 * (no result payloads stored), and clearable. Persisted the same way
 * `useTableDensityStore` persists a preference: `localStorage` only,
 * never synced or shared across devices/accounts.
 */
export const useRecentSearchesStore = create<RecentSearchesState>()(
  persist(
    (set) => ({
      terms: [],
      addSearch: (term) =>
        set((state) => {
          const trimmed = term.trim();
          if (trimmed.length < 2) return state;
          const withoutDuplicate = state.terms.filter((existing) => existing.toLowerCase() !== trimmed.toLowerCase());
          return { terms: [trimmed, ...withoutDuplicate].slice(0, MAX_RECENT_SEARCHES) };
        }),
      clear: () => set({ terms: [] }),
    }),
    { name: "aiios-recent-searches", storage: createJSONStorage(() => localStorage) },
  ),
);
