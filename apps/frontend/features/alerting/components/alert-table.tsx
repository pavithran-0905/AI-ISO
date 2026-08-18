"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SEVERITY_LABEL, SEVERITY_TONE } from "@/features/alerting/lib/severity";
import type { Alert } from "@/features/alerting/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

export type AlertSortField = "title" | "source" | "severity" | "status" | "triggeredAt";

const COLUMNS: { field: AlertSortField; label: string }[] = [
  { field: "title", label: "Alert" },
  { field: "source", label: "Source" },
  { field: "severity", label: "Severity" },
  { field: "status", label: "Status" },
  { field: "triggeredAt", label: "Triggered" },
];

/**
 * Sorted entirely client-side (§6) — legitimate here only because the
 * `alerts` array passed in is already the endpoint's complete,
 * unpaginated result for the active status/severity filter; there's no
 * remainder being silently left out of the sort. Below `md`, falls back
 * to a stacked card list (§32), matching `AssetTable`.
 */
export function AlertTable({
  alerts,
  sortField,
  sortDirection,
  onSortChange,
}: {
  alerts: Alert[];
  sortField: AlertSortField;
  sortDirection: "asc" | "desc";
  onSortChange: (field: AlertSortField) => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-3";

  return (
    <div className="flex flex-col gap-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              {COLUMNS.map((column) => (
                <th key={column.field} scope="col" className={cn(cellPadding, "font-medium")}>
                  <button
                    type="button"
                    onClick={() => onSortChange(column.field)}
                    className="hover:text-foreground text-muted-foreground focus-visible:ring-ring flex items-center gap-1 rounded focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {column.label}
                    {sortField === column.field ? (
                      sortDirection === "asc" ? (
                        <ArrowUp className="size-3.5" aria-hidden="true" />
                      ) : (
                        <ArrowDown className="size-3.5" aria-hidden="true" />
                      )
                    ) : (
                      <ArrowUpDown className="size-3.5 opacity-40" aria-hidden="true" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                <td className={cellPadding}>
                  <Link
                    href={`/alerting/alerts/${alert.id}`}
                    className="focus-visible:ring-ring rounded font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {alert.title}
                  </Link>
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{alert.source}</td>
                <td className={cellPadding}>
                  <StatusBadge tone={SEVERITY_TONE[alert.severity]} label={SEVERITY_LABEL[alert.severity]} />
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{alert.status}</td>
                <td className={cn(cellPadding, "text-muted-foreground")}>
                  <time dateTime={alert.triggeredAt}>{formatRelativeTime(alert.triggeredAt)}</time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {alerts.map((alert) => (
          <li key={alert.id}>
            <Link href={`/alerting/alerts/${alert.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-sm font-medium">{alert.title}</p>
                    <p className="text-muted-foreground text-xs">
                      {alert.source} · <time dateTime={alert.triggeredAt}>{formatRelativeTime(alert.triggeredAt)}</time>
                    </p>
                  </div>
                  <StatusBadge tone={SEVERITY_TONE[alert.severity]} label={SEVERITY_LABEL[alert.severity]} className="shrink-0" />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <p className="text-muted-foreground text-sm">
        {alerts.length} alert{alerts.length === 1 ? "" : "s"}
      </p>
      {alerts.length > 0 && (
        <p className="sr-only" aria-live="polite">
          Showing {alerts.length} alerts.
        </p>
      )}
    </div>
  );
}
