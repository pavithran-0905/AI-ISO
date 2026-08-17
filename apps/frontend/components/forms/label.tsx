import type { LabelHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

/** A real `<label>`, always — §14 forbids placeholder-as-only-label,
 * and an unassociated visual label is invisible to a screen reader
 * regardless. Pair with `htmlFor`/`id`, or wrap the control. */
export function Label({ className, children, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-xs font-medium", className)} {...props}>
      {children}
    </label>
  );
}
