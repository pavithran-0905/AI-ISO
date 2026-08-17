import type { InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Drives both the visual error state and `aria-invalid` — pass the
   * same boolean a `FormField`'s own error message is conditioned on. */
  invalid?: boolean;
}

/**
 * The base text input (§12/§14). Every state (default/hover/focus/
 * disabled/readonly/invalid) is handled here so no feature reinvents
 * input styling — see `FormField` for the label/description/error
 * composition wrapper.
 */
export function Input({ invalid = false, className, ...props }: InputProps) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={cn(
        "bg-input border-border h-9 w-full rounded-md border px-3 text-sm transition-colors",
        "placeholder:text-muted-foreground",
        "hover:border-muted-foreground/50",
        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
        "disabled:pointer-events-none disabled:opacity-50",
        "read-only:bg-muted read-only:cursor-default",
        invalid && "border-danger focus-visible:ring-danger",
        className,
      )}
      {...props}
    />
  );
}
