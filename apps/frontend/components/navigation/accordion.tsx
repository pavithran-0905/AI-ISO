import { ChevronDown } from "lucide-react";

import { cn } from "@/utils/cn";

export interface AccordionItem {
  id: string;
  title: string;
  content: React.ReactNode;
  defaultOpen?: boolean;
}

/**
 * A vertically-stacked disclosure list (§12), built on native
 * `<details>`/`<summary>` — expand/collapse, keyboard toggling (Enter/
 * Space on the summary), and independent open state per item all come
 * from the platform for free. Each item opens/closes independently
 * (the common "accordion" shape); nothing here enforces single-open
 * exclusivity, since most enterprise use cases don't want it.
 */
export function Accordion({ items, className }: { items: AccordionItem[]; className?: string }) {
  return (
    <div className={cn("divide-border divide-y rounded-lg border border-border", className)}>
      {items.map((item) => (
        <details key={item.id} open={item.defaultOpen} className="group">
          <summary
            className={cn(
              "flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium",
              "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
              "[&::-webkit-details-marker]:hidden",
            )}
          >
            {item.title}
            <ChevronDown className="text-muted-foreground size-4 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>
          <div className="text-muted-foreground px-4 pb-3 text-sm">{item.content}</div>
        </details>
      ))}
    </div>
  );
}
