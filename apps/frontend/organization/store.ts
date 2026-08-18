import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface OrganizationState {
  /** Which organization's data the dashboard (and any future org-scoped
   * feature) is currently showing. `null` until the user picks one, or
   * forever if they only have access to one and it was auto-selected —
   * see `useSelectedOrganization`. Persisted (unlike session-only UI
   * state) because re-picking an organization on every page load would
   * be pure friction, and — unlike an auth token — this value carries
   * no sensitivity: it's just an id the user already has read access to. */
  selectedOrganizationId: string | null;
  setSelectedOrganizationId: (id: string | null) => void;
}

export const useOrganizationStore = create<OrganizationState>()(
  persist(
    (set) => ({
      selectedOrganizationId: null,
      setSelectedOrganizationId: (id) => set({ selectedOrganizationId: id }),
    }),
    { name: "aiios-organization", storage: createJSONStorage(() => localStorage) },
  ),
);
