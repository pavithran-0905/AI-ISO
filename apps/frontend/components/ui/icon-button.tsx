import { Loader2, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

import { iconSize } from "@/lib/icons";
import { cn } from "@/utils/cn";
import type { ButtonVariant } from "@/components/ui/button";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  /** Required, not optional — an icon-only control with no accessible
   * name fails §21 ("every interactive component must have an
   * accessible name") the moment it ships. */
  "aria-label": string;
  icon: LucideIcon;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/90",
  secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
  outline: "border border-border bg-transparent hover:bg-muted",
  ghost: "bg-transparent hover:bg-muted",
  danger: "bg-danger text-danger-foreground hover:bg-danger/90",
};

/** The icon-only counterpart to `Button` (§12). A square hit target at
 * `iconSize.control`, never used for a labeled action `Button` could
 * serve instead. */
export function IconButton({
  variant = "ghost",
  loading = false,
  disabled,
  className,
  icon: Icon,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex size-8 items-center justify-center rounded-md transition-colors",
        "disabled:pointer-events-none disabled:opacity-50",
        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
        VARIANT_CLASSES[variant],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading}
      {...props}
    >
      {loading ? (
        <Loader2 className={cn(iconSize.control, "animate-spin motion-reduce:animate-none")} aria-hidden="true" />
      ) : (
        <Icon className={iconSize.control} aria-hidden="true" />
      )}
    </button>
  );
}
