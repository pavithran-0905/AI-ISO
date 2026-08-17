import { create } from "zustand";

import type { AlertTone } from "@/components/feedback/alert";

export interface ToastRecord {
  id: string;
  tone: AlertTone;
  title: string;
  description?: string;
}

interface ToastState {
  toasts: ToastRecord[];
  dismiss: (id: string) => void;
}

const DEFAULT_DURATION_MS = 5000;

export const useToastStore = create<ToastState>()((set) => ({
  toasts: [],
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
}));

/**
 * The imperative Toast API (§12) — `toast.success("Saved")` from
 * anywhere (an event handler, a mutation's `onSuccess`), no component
 * tree position required. Auto-dismisses after 5s; the rendered toast
 * (`components/feedback/toast.tsx`) also offers a manual dismiss.
 */
function push(tone: AlertTone, title: string, description?: string): void {
  const id = crypto.randomUUID();
  useToastStore.setState((state) => ({ toasts: [...state.toasts, { id, tone, title, description }] }));
  setTimeout(() => useToastStore.getState().dismiss(id), DEFAULT_DURATION_MS);
}

export const toast = {
  info: (title: string, description?: string) => push("info", title, description),
  success: (title: string, description?: string) => push("success", title, description),
  warning: (title: string, description?: string) => push("warning", title, description),
  danger: (title: string, description?: string) => push("danger", title, description),
};
