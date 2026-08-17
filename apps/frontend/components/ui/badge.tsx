import type { HTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export type BadgeVariant = "default" | "outline" | "primary";

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-muted text-muted-foreground",
  outline: "border border-border text-foreground",
  primary: "bg-primary/15 text-primary",
};

/**
 * A generic, non-status badge (§12) — counts, tags, categories. For an
 * operational state, use `StatusIndicator`/`StatusBadge` instead: a
 * plain `Badge` intentionally carries no tone-based meaning.
 */
export function Badge({
  variant = "default",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        VARIANT_CLASSES[variant],
        className,
      )}
      {...props}
    />
  );
}
