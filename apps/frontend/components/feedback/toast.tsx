"use client";

import { X } from "lucide-react";

import { Alert } from "@/components/feedback/alert";
import { IconButton } from "@/components/ui/icon-button";
import { useToastStore } from "@/state/toast-store";

/**
 * The toast viewport (§12) — mounted once, in `AppProviders`, rendering
 * whatever `useToastStore` currently holds. `aria-live="polite"`: a
 * toast is important enough to announce but not urgent enough to
 * interrupt (contrast `Alert`'s own `role="alert"` for a
 * warning/danger tone, which *is* assertive).
 */
export function ToastViewport() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="fixed right-4 bottom-4 z-toast flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((item) => (
        <div key={item.id} className="relative motion-safe:animate-overlay-in">
          <Alert tone={item.tone} title={item.title}>
            {item.description}
          </Alert>
          <IconButton
            icon={X}
            aria-label="Dismiss notification"
            variant="ghost"
            className="absolute top-1 right-1 size-6"
            onClick={() => dismiss(item.id)}
          />
        </div>
      ))}
    </div>
  );
}
