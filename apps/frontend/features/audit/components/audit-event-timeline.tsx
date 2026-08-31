"use client";

import { StatusBadge } from "@/components/feedback/status-badge";
import { formatActionLabel } from "@/features/audit/lib/format";
import type { AuditEvent, AuditEventSearchResult } from "@/features/audit/types";

function resourceLabel(event: AuditEvent): string {
  if (event.entityReference) return event.entityReference;
  if (event.entityId) return `${event.entityType} · ${event.entityId}`;
  return event.entityType;
}

/**
 * §21's alternate view over the exact same `result` the table renders
 * — no separate fetch (§22). Built as a real `<ol>`, which is itself
 * the "accessible structured equivalent" §46 requires: a screen reader
 * announces it as an ordered list of N items with no extra markup, not
 * a purely visual timeline needing a hidden fallback table.
 */
export function AuditEventTimeline({ result }: { result: AuditEventSearchResult }) {
  return (
    <ol className="flex flex-col gap-4 border-l border-border pl-4">
      {result.items.map((event) => (
        <li key={event.id} className="relative">
          <span className="bg-primary absolute top-1.5 -left-[21px] size-2 rounded-full" aria-hidden="true" />
          <time dateTime={event.occurredAt} className="text-muted-foreground text-xs">
            {new Date(event.occurredAt).toLocaleString()}
          </time>
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">{formatActionLabel(event.action)}</p>
            <StatusBadge tone={event.succeeded ? "success" : "danger"} label={event.succeeded ? "Success" : "Failure"} />
          </div>
          <p className="text-muted-foreground text-sm">{resourceLabel(event)}</p>
        </li>
      ))}
    </ol>
  );
}
