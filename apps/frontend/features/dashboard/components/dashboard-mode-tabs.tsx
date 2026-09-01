"use client";

import { cn } from "@/utils/cn";
import type { DashboardModeValue } from "@/features/dashboard/lib/widget-registry";

const MODE_ITEMS: { id: DashboardModeValue; label: string }[] = [
  { id: "executive", label: "Executive" },
  { id: "operations", label: "Operations" },
];

/**
 * §5's dashboard-mode switch. Deliberately not built on the shared
 * `Tabs` primitive: `Tabs` pairs one tablist with exactly one
 * `tabpanel` it renders itself, but a mode here doesn't own a single
 * panel — it changes which of several independent widget cards are
 * visible across the whole page. Reusing `Tabs` anyway would mean an
 * empty, misleading `tabpanel` pointing nowhere near the real content
 * (§46: accessible structure). A `radiogroup` of two mutually-exclusive
 * options is the correct native pattern for that shape instead — still
 * one shared primitive class of control, just the right one.
 */
export function DashboardModeTabs({ mode, onChange }: { mode: DashboardModeValue; onChange: (mode: DashboardModeValue) => void }) {
  return (
    <div role="radiogroup" aria-label="Dashboard mode" className="border-border bg-muted/40 inline-flex gap-0.5 rounded-lg border p-0.5">
      {MODE_ITEMS.map((item) => {
        const selected = item.id === mode;
        return (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(item.id)}
            className={cn(
              "focus-visible:ring-ring rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none",
              selected ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
