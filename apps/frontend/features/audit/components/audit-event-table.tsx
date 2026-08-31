"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { formatActionLabel } from "@/features/audit/lib/format";
import type { AuditEvent, AuditEventSearchResult } from "@/features/audit/types";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

function resourceLabel(event: AuditEvent): string {
  if (event.entityReference) return event.entityReference;
  if (event.entityId) return `${event.entityType} · ${event.entityId}`;
  return event.entityType;
}

/**
 * §7's "enterprise-grade activity table" — one source's events at a
 * time (never merged across sources, see `AuditEventSearchResult`'s
 * docstring). Real offset/limit pagination; `hasMore` is a heuristic
 * (`items.length === limit`), the same honest approach as
 * `features/administration/components/user-table.tsx`, since none of
 * the three audit routes returns a total count.
 */
export function AuditEventTable({
  result,
  onPageChange,
  onSelectEvent,
}: {
  result: AuditEventSearchResult;
  onPageChange: (offset: number) => void;
  onSelectEvent: (event: AuditEvent) => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-3";
  const page = Math.floor(result.offset / result.limit) + 1;

  return (
    <div className="flex flex-col gap-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              <th scope="col" className={cn(cellPadding, "font-medium")}>Time</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Actor</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Action</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Resource</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Status</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                <span className="sr-only">Details</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {result.items.map((event) => (
              <tr key={event.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                <td className={cn(cellPadding, "text-muted-foreground whitespace-nowrap")}>
                  <time dateTime={event.occurredAt}>{new Date(event.occurredAt).toLocaleString()}</time>
                </td>
                <td className={cn(cellPadding, "font-mono text-xs")}>{event.actorId ?? "—"}</td>
                <td className={cellPadding}>{formatActionLabel(event.action)}</td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{resourceLabel(event)}</td>
                <td className={cellPadding}>
                  <StatusBadge tone={event.succeeded ? "success" : "danger"} label={event.succeeded ? "Success" : "Failure"} />
                </td>
                <td className={cellPadding}>
                  <Button variant="ghost" onClick={() => onSelectEvent(event)}>
                    View
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {result.items.map((event) => (
          <li key={event.id}>
            <Card className="hover:border-muted-foreground/50 cursor-pointer transition-colors" onClick={() => onSelectEvent(event)}>
              <CardContent className="flex flex-col gap-1 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">{formatActionLabel(event.action)}</p>
                  <StatusBadge tone={event.succeeded ? "success" : "danger"} label={event.succeeded ? "Success" : "Failure"} />
                </div>
                <p className="text-muted-foreground text-xs">{resourceLabel(event)}</p>
                <p className="text-muted-foreground text-xs">
                  <time dateTime={event.occurredAt}>{new Date(event.occurredAt).toLocaleString()}</time>
                </p>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground">
          Page {page} · {result.items.length} shown
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={result.offset <= 0} onClick={() => onPageChange(Math.max(0, result.offset - result.limit))}>
            Previous
          </Button>
          <Button variant="outline" disabled={!result.hasMore} onClick={() => onPageChange(result.offset + result.limit)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
