"use client";

import { useRef } from "react";

import { useDismissableLayer } from "@/components/overlays/use-dismissable-layer";
import { cn } from "@/utils/cn";

export interface PopoverProps {
  open: boolean;
  onClose: () => void;
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "start" | "end";
  className?: string;
}

/**
 * A click-triggered floating panel anchored to its trigger (§12) — for
 * arbitrary content (a filter form, a details preview). For an action
 * list, use `Dropdown` instead, which adds menu semantics/keyboard
 * navigation on top of the same positioning shape.
 */
export function Popover({ open, onClose, trigger, children, align = "start", className }: PopoverProps) {
  const ref = useRef<HTMLDivElement>(null);
  useDismissableLayer(open, ref, onClose);

  return (
    <div ref={ref} className="relative inline-block">
      {trigger}
      {open && (
        <div
          className={cn(
            "bg-surface-elevated border-border absolute z-dropdown mt-1.5 min-w-48 rounded-lg border p-3 shadow-elevation-3",
            "motion-safe:animate-overlay-in",
            align === "start" ? "left-0" : "right-0",
            className,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
