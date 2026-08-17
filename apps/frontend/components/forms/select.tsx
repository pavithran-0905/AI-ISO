import { ChevronDown } from "lucide-react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

/**
 * A styled native `<select>` (§12) — deliberately not a custom
 * listbox: a native select gets keyboard navigation, typeahead, and
 * mobile-native pickers for free, with zero extra dependency or ARIA
 * to get wrong. A custom `Dropdown`/menu component exists separately
 * for non-form action menus.
 */
export function Select({ invalid = false, className, children, ...props }: SelectProps) {
  return (
    <div className="relative">
      <select
        aria-invalid={invalid || undefined}
        className={cn(
          "bg-input border-border h-9 w-full appearance-none rounded-md border pr-8 pl-3 text-sm transition-colors",
          "hover:border-muted-foreground/50",
          "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
          "disabled:pointer-events-none disabled:opacity-50",
          invalid && "border-danger focus-visible:ring-danger",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="text-muted-foreground pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
