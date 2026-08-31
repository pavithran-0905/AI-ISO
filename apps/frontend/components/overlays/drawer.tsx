"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/utils/cn";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

/**
 * An edge-anchored panel (§12) — for a longer-form task (a detail
 * view, a multi-field create form) that doesn't warrant losing the
 * page context entirely. Built on the same native `<dialog>` primitive
 * as `Dialog`, for the same reason (real focus trap, top-layer,
 * Escape-to-close for free) — only the positioning/sizing differs.
 */
export function Drawer({ open, onClose, title, children, footer, className }: DrawerProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      aria-labelledby="drawer-title"
      className={cn(
        // A closed native `<dialog>` relies on the UA stylesheet's
        // `dialog:not([open]) { display: none }` — but that's a
        // *user-agent*-origin rule, which always loses to an
        // author-origin rule of the same importance regardless of
        // specificity. An unconditional `flex` utility here would
        // therefore keep this fixed, full-height, right-anchored panel
        // laid out (and intercepting clicks) even while closed —
        // confirmed via a real Chromium E2E run, not just reasoning
        // about the cascade. `hidden open:flex` is the standard fix:
        // default closed (`display: none`, itself author-origin and
        // so able to seat under the UA rule), `flex` only once the
        // browser has actually set `[open]`.
        "bg-surface-elevated text-foreground fixed inset-y-0 right-0 m-0 hidden h-full max-h-none w-full max-w-md flex-col open:flex",
        "border-l border-border p-0 shadow-elevation-3",
        "backdrop:bg-foreground/40",
        "motion-safe:open:animate-drawer-in",
        className,
      )}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="flex items-center justify-between gap-4 border-b border-border p-4">
        <h2 id="drawer-title" className="text-sm font-semibold">
          {title}
        </h2>
        <IconButton icon={X} aria-label="Close panel" onClick={onClose} />
      </div>
      {children && <div className="flex-1 overflow-auto p-4">{children}</div>}
      {footer && <div className="flex justify-end gap-2 border-t border-border p-4">{footer}</div>}
    </dialog>
  );
}
