"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Star } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { IconButton } from "@/components/ui/icon-button";
import { StatusBadge } from "@/components/feedback/status-badge";
import type { Report } from "@/features/reporting/types";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

export type ReportSortField = "name" | "category" | "reportType";

const COLUMNS: { field: ReportSortField; label: string }[] = [
  { field: "name", label: "Report" },
  { field: "category", label: "Category" },
  { field: "reportType", label: "Type" },
];

/**
 * The reports table (§5). Columns are exactly the real fields
 * `ReportResponse` has — no "Updated"/"Last generated"/"Schedule"
 * columns (confirmed no timestamp fields exist on this response at
 * all; schedule status would need a per-report extra fetch this table
 * doesn't do — see `docs/frontend/backend-v1-integration-limitations.md`).
 * Below `md`, falls back to a stacked card list (§32), matching
 * `AssetTable`/`AlertTable`.
 */
export function ReportTable({
  reports,
  favoriteIds,
  onToggleFavorite,
  sortField,
  sortDirection,
  onSortChange,
}: {
  reports: Report[];
  favoriteIds: ReadonlySet<string>;
  onToggleFavorite: (reportId: string, favorited: boolean) => void;
  sortField: ReportSortField;
  sortDirection: "asc" | "desc";
  onSortChange: (field: ReportSortField) => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-3";

  return (
    <div className="flex flex-col gap-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              <th scope="col" className={cn(cellPadding, "w-10")}>
                <span className="sr-only">Favorite</span>
              </th>
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
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Format
              </th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {reports.map((report) => {
              const favorited = favoriteIds.has(report.id);
              return (
                <tr key={report.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                  <td className={cellPadding}>
                    <IconButton
                      icon={Star}
                      aria-label={favorited ? "Unfavorite report" : "Favorite report"}
                      aria-pressed={favorited}
                      variant="ghost"
                      className={favorited ? "text-warning" : undefined}
                      onClick={() => onToggleFavorite(report.id, favorited)}
                    />
                  </td>
                  <td className={cellPadding}>
                    <Link
                      href={`/reporting/reports/${report.id}`}
                      className="focus-visible:ring-ring rounded font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
                    >
                      {report.name}
                    </Link>
                  </td>
                  <td className={cn(cellPadding, "text-muted-foreground")}>{report.category}</td>
                  <td className={cn(cellPadding, "text-muted-foreground")}>{report.reportType}</td>
                  <td className={cn(cellPadding, "text-muted-foreground uppercase")}>{report.defaultFormat}</td>
                  <td className={cellPadding}>
                    <StatusBadge tone={report.enabled ? "success" : "neutral"} label={report.enabled ? "Enabled" : "Disabled"} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {reports.map((report) => {
          const favorited = favoriteIds.has(report.id);
          return (
            <li key={report.id}>
              <Card>
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <Link href={`/reporting/reports/${report.id}`} className="flex-1">
                    <p className="text-sm font-medium">{report.name}</p>
                    <p className="text-muted-foreground text-xs">
                      {report.category} · {report.reportType}
                    </p>
                  </Link>
                  <IconButton
                    icon={Star}
                    aria-label={favorited ? "Unfavorite report" : "Favorite report"}
                    aria-pressed={favorited}
                    variant="ghost"
                    className={favorited ? "text-warning" : undefined}
                    onClick={() => onToggleFavorite(report.id, favorited)}
                  />
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>

      <p className="text-muted-foreground text-sm">
        {reports.length} report{reports.length === 1 ? "" : "s"}
      </p>
    </div>
  );
}
