import { create } from "zustand";

interface CommandPaletteState {
  open: boolean;
  show: () => void;
  hide: () => void;
  toggle: () => void;
}

/**
 * Global open/closed state for the command palette (docs/frontend
 * Prompt 003 §15) — a plain (non-persisted) store, since "is the
 * palette open right now" is transient UI state, not a preference. A
 * store rather than component-local state so both the header's own
 * trigger button and the global Ctrl/Cmd+K listener can open it
 * without a shared parent needing to own the state.
 */
export const useCommandPaletteStore = create<CommandPaletteState>()((set) => ({
  open: false,
  show: () => set({ open: true }),
  hide: () => set({ open: false }),
  toggle: () => set((state) => ({ open: !state.open })),
}));
