import type { InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

/**
 * A native `<input type="checkbox">`, tinted via CSS `accent-color`
 * (§12) — real keyboard/screen-reader behavior for free, no custom
 * listbox-style reimplementation. Always pair with a `Label` (via
 * `htmlFor`) or wrap it: §14/§21 apply here too.
 */
export function Checkbox({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="checkbox"
      className={cn(
        "accent-primary size-4 rounded",
        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
