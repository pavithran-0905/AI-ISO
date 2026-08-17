import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SidebarState {
  collapsed: boolean;
  toggle: () => void;
  setCollapsed: (collapsed: boolean) => void;
  /** Which nav groups are expanded (nested groups start expanded by
   * default — collapsing one is an explicit user action worth
   * remembering, matching the collapsed/expanded persistence
   * requirement in docs/frontend Prompt 003 §10). */
  collapsedGroups: Record<string, boolean>;
  toggleGroup: (group: string) => void;
}

/**
 * Sidebar collapse preference (docs/frontend Prompt 003 §10: "Persist
 * sidebar preference using the existing frontend client-state
 * architecture") — the same `persist`-backed Zustand pattern
 * `state/theme-store.ts` already established in Prompt 001.
 */
export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      collapsed: false,
      toggle: () => set((state) => ({ collapsed: !state.collapsed })),
      setCollapsed: (collapsed) => set({ collapsed }),
      collapsedGroups: {},
      toggleGroup: (group) =>
        set((state) => ({
          collapsedGroups: { ...state.collapsedGroups, [group]: !state.collapsedGroups[group] },
        })),
    }),
    { name: "aiios-sidebar" },
  ),
);
