"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Button } from "@/components/ui/button";
import { ASSET_HEALTH_TO_STATUS } from "@/features/infrastructure/lib/status-maps";
import type { Asset, AssetPagination } from "@/features/infrastructure/types";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

export type AssetSortField = "name" | "asset_type" | "status" | "health" | "environment" | "updated_at";

const COLUMNS: { field: AssetSortField; label: string }[] = [
  { field: "name", label: "Asset" },
  { field: "asset_type", label: "Type" },
  { field: "status", label: "Status" },
  { field: "health", label: "Health" },
  { field: "environment", label: "Environment" },
  { field: "updated_at", label: "Updated" },
];

/**
 * The asset inventory table. Columns are exactly the real
 * `AssetResponse` fields most useful at a glance — no "Last Seen"
 * column (no such field exists on the backend response; `updatedAt`
 * stands in and is labeled "Updated"). Sorting maps directly onto
 * `GET /inventory/search`'s own `sort=field:asc|desc` syntax. Below
 * `md`, falls back to a stacked card list rather than a
 * horizontally-scrolling table.
 */
export function AssetTable({
  assets,
  pagination,
  sortField,
  sortDirection,
  onSortChange,
  onPageChange,
}: {
  assets: Asset[];
  pagination: AssetPagination;
  sortField: AssetSortField;
  sortDirection: "asc" | "desc";
  onSortChange: (field: AssetSortField) => void;
  onPageChange: (page: number) => void;
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
            {assets.map((asset) => (
              <tr key={asset.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                <td className={cellPadding}>
                  <Link
                    href={`/infrastructure/assets/${asset.id}`}
                    className="focus-visible:ring-ring rounded font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {asset.displayName ?? asset.name}
                  </Link>
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{asset.assetType}</td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{asset.status}</td>
                <td className={cellPadding}>
                  <StatusIndicator state={ASSET_HEALTH_TO_STATUS[asset.health]} />
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{asset.environment ?? "—"}</td>
                <td className={cn(cellPadding, "text-muted-foreground")}>
                  <time dateTime={asset.updatedAt}>{new Date(asset.updatedAt).toLocaleDateString()}</time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {assets.map((asset) => (
          <li key={asset.id}>
            <Link href={`/infrastructure/assets/${asset.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-sm font-medium">{asset.displayName ?? asset.name}</p>
                    <p className="text-muted-foreground text-xs">
                      {asset.assetType} · {asset.environment ?? "—"}
                    </p>
                  </div>
                  <StatusIndicator state={ASSET_HEALTH_TO_STATUS[asset.health]} />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground">
          {pagination.total} asset{pagination.total === 1 ? "" : "s"} · page {pagination.page} of{" "}
          {Math.max(pagination.totalPages, 1)}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            disabled={!pagination.hasPrevious}
            onClick={() => onPageChange(pagination.page - 1)}
          >
            Previous
          </Button>
          <Button variant="outline" disabled={!pagination.hasNext} onClick={() => onPageChange(pagination.page + 1)}>
            Next
          </Button>
        </div>
      </div>
      {assets.length > 0 && (
        <p className="sr-only" aria-live="polite">
          Showing {assets.length} assets, page {pagination.page} of {Math.max(pagination.totalPages, 1)}.
        </p>
      )}
    </div>
  );
}
