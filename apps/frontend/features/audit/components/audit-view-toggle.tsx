"use client";

import { List, Rows3 } from "lucide-react";

import { cn } from "@/utils/cn";

export type AuditViewMode = "table" | "timeline";

/** §22: a plain toggle over the same already-fetched `result` both
 * `AuditEventTable` and `AuditEventTimeline` render — switching never
 * triggers a new fetch. */
export function AuditViewToggle({ value, onChange }: { value: AuditViewMode; onChange: (mode: AuditViewMode) => void }) {
  return (
    <div role="radiogroup" aria-label="Event display" className="border-border inline-flex rounded-md border p-0.5">
      {(
        [
          { mode: "table" as const, label: "Table", icon: List },
          { mode: "timeline" as const, label: "Timeline", icon: Rows3 },
        ]
      ).map(({ mode, label, icon: Icon }) => (
        <button
          key={mode}
          type="button"
          role="radio"
          aria-checked={value === mode}
          onClick={() => onChange(mode)}
          className={cn(
            "focus-visible:ring-ring inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none",
            value === mode ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon className="size-4" aria-hidden="true" />
          {label}
        </button>
      ))}
    </div>
  );
}
