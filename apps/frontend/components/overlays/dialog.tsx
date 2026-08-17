"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/utils/cn";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

/**
 * A modal dialog (§12), built on the native `<dialog>` element rather
 * than a hand-rolled portal + focus trap: `showModal()` gives real
 * focus trapping, top-layer rendering above everything else including
 * `position: fixed` ancestors, a native `::backdrop`, and Escape-to-close
 * for free — no dependency, no bug-prone reimplementation of behavior
 * the platform already provides correctly. `onClose` fires from the
 * dialog's own native `close` event, so it also fires on Escape.
 */
export function Dialog({ open, onClose, title, description, children, footer, className }: DialogProps) {
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
      aria-labelledby="dialog-title"
      aria-describedby={description ? "dialog-description" : undefined}
      className={cn(
        "bg-surface-elevated text-foreground w-full max-w-md rounded-lg border border-border p-0 shadow-elevation-3",
        "backdrop:bg-foreground/40",
        "motion-safe:open:animate-dialog-in",
        className,
      )}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="flex items-start justify-between gap-4 border-b border-border p-4">
        <div className="flex flex-col gap-1">
          <h2 id="dialog-title" className="text-sm font-semibold">
            {title}
          </h2>
          {description && (
            <p id="dialog-description" className="text-muted-foreground text-xs">
              {description}
            </p>
          )}
        </div>
        <IconButton icon={X} aria-label="Close dialog" onClick={onClose} />
      </div>
      {children && <div className="p-4">{children}</div>}
      {footer && <div className="flex justify-end gap-2 border-t border-border p-4">{footer}</div>}
    </dialog>
  );
}
