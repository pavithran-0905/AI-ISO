import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

/** The multi-line counterpart to `Input` — same state handling. */
export function Textarea({ invalid = false, className, ...props }: TextareaProps) {
  return (
    <textarea
      aria-invalid={invalid || undefined}
      className={cn(
        "bg-input border-border min-h-20 w-full rounded-md border px-3 py-2 text-sm transition-colors",
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
