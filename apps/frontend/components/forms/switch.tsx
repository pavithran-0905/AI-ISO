import type { InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "role"> {
  "aria-label"?: string;
}

/**
 * A toggle switch (§12). No native HTML element for this exists, so
 * it's a real `<input type="checkbox" role="switch">` — genuinely
 * focusable/toggleable/screen-reader-announced as a switch, not a
 * `<div>` with a click handler — visually hidden (`peer sr-only`)
 * behind a styled track/thumb built with `peer-checked:`/
 * `peer-focus-visible:` so the real input still drives every state.
 */
export function Switch({ className, ...props }: SwitchProps) {
  return (
    <label className={cn("relative inline-flex h-5 w-9 shrink-0 cursor-pointer", className)}>
      <input type="checkbox" role="switch" className="peer sr-only" {...props} />
      <span
        className={cn(
          "bg-muted peer-checked:bg-primary absolute inset-0 rounded-full transition-colors",
          "peer-focus-visible:ring-ring peer-focus-visible:ring-2 peer-focus-visible:ring-offset-2",
          "peer-disabled:pointer-events-none peer-disabled:opacity-50",
        )}
        aria-hidden="true"
      />
      <span
        className={cn(
          "bg-background absolute top-0.5 left-0.5 size-4 rounded-full shadow-elevation-1 transition-transform",
          "peer-checked:translate-x-4",
        )}
        aria-hidden="true"
      />
    </label>
  );
}
