import type { InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

/** A native `<input type="radio">`, tinted via CSS `accent-color` —
 * same rationale as `Checkbox`. Group with a shared `name` and a
 * `<fieldset>`/`<legend>` for the group's own accessible name. */
export function Radio({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="radio"
      className={cn(
        "accent-primary size-4",
        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
