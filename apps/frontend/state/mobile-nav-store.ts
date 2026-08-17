import { create } from "zustand";

interface MobileNavState {
  open: boolean;
  show: () => void;
  hide: () => void;
  toggle: () => void;
}

/**
 * Open/closed state for the narrow-viewport navigation drawer (§11:
 * "Navigation becomes an accessible drawer/sheet"). A plain
 * (non-persisted) store, same shape as `command-palette-store` — the
 * header's hamburger trigger and `PrimaryNavigation`'s own drawer don't
 * share a parent, so both read/write this instead of lifting state.
 */
export const useMobileNavStore = create<MobileNavState>()((set) => ({
  open: false,
  show: () => set({ open: true }),
  hide: () => set({ open: false }),
  toggle: () => set((state) => ({ open: !state.open })),
}));
