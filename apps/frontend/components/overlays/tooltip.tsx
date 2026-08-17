"use client";

import { cloneElement, isValidElement, useId } from "react";

import { cn } from "@/utils/cn";

export type TooltipSide = "top" | "bottom" | "left" | "right";

const SIDE_CLASSES: Record<TooltipSide, string> = {
  top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
  left: "right-full top-1/2 mr-1.5 -translate-y-1/2",
  right: "left-full top-1/2 ml-1.5 -translate-y-1/2",
};

/**
 * A hover/focus-triggered label (§12). CSS-only (`group-hover`/
 * `group-focus-within`) rather than JS-driven positioning — simple,
 * correct for a trigger with a known static position (the overwhelming
 * majority of tooltip usage: an icon button, a truncated cell), and
 * avoids a floating-position dependency for a component that doesn't
 * need one. `children` must be a single element; it receives
 * `aria-describedby` wiring it to the tooltip bubble.
 */
export function Tooltip({
  label,
  side = "top",
  children,
}: {
  label: string;
  side?: TooltipSide;
  children: React.ReactElement<{ "aria-describedby"?: string }>;
}) {
  const id = useId();
  if (!isValidElement(children)) return children;

  const trigger = cloneElement(children, { "aria-describedby": id });

  return (
    <span className="group relative inline-flex">
      {trigger}
      <span
        role="tooltip"
        id={id}
        className={cn(
          "bg-foreground text-background pointer-events-none absolute z-tooltip rounded-md px-2 py-1 text-xs whitespace-nowrap",
          "opacity-0 transition-opacity motion-reduce:transition-none",
          "group-hover:opacity-100 group-focus-within:opacity-100",
          SIDE_CLASSES[side],
        )}
      >
        {label}
      </span>
    </span>
  );
}
