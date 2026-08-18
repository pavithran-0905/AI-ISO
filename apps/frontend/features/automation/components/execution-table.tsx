"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { executionDurationMs, formatDurationMs } from "@/features/automation/lib/duration";
import { EXECUTION_STATUS_TO_STATUS } from "@/features/automation/lib/status-maps";
import type { AutomationExecution } from "@/features/automation/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

export type ExecutionSortField = "createdAt" | "status" | "duration";

const COLUMNS: { field: ExecutionSortField; label: string }[] = [
  { field: "status", label: "Status" },
  { field: "createdAt", label: "Started" },
  { field: "duration", label: "Duration" },
];

/**
 * The executions table (§7). Columns are exactly the fields
 * `AutomationExecutionResponse` really has, plus a client-computed
 * Duration (no such field exists on the response) and an Automation
 * name resolved by the caller against the jobs list — the execution
 * itself carries only a bare `job_id`.
 *
 * Below `md`, falls back to a stacked card list (§36), matching
 * `AssetTable`/`AlertTable`/`ReportTable`.
 */
export function ExecutionTable({
  executions,
  jobNameById,
  sortField,
  sortDirection,
  onSortChange,
}: {
  executions: AutomationExecution[];
  jobNameById: ReadonlyMap<string, string>;
  sortField: ExecutionSortField;
  sortDirection: "asc" | "desc";
  onSortChange: (field: ExecutionSortField) => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-3";

  return (
    <div className="flex flex-col gap-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Automation
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
                Mode
              </th>
            </tr>
          </thead>
          <tbody>
            {executions.map((execution) => (
              <tr key={execution.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                <td className={cellPadding}>
                  <Link
                    href={`/automation/executions/${execution.id}`}
                    className="focus-visible:ring-ring rounded font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {jobNameById.get(execution.jobId) ?? `Run ${execution.id.slice(0, 8)}`}
                  </Link>
                </td>
                <td className={cellPadding}>
                  <StatusIndicator state={EXECUTION_STATUS_TO_STATUS[execution.status]} />
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>
                  <time dateTime={execution.startedAt ?? execution.createdAt}>
                    {formatRelativeTime(execution.startedAt ?? execution.createdAt)}
                  </time>
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>
                  {formatDurationMs(executionDurationMs(execution)) ?? "—"}
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{execution.executionMode.replace(/_/g, " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {executions.map((execution) => (
          <li key={execution.id}>
            <Link href={`/automation/executions/${execution.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-sm font-medium">{jobNameById.get(execution.jobId) ?? `Run ${execution.id.slice(0, 8)}`}</p>
                    <p className="text-muted-foreground text-xs">
                      <time dateTime={execution.startedAt ?? execution.createdAt}>
                        {formatRelativeTime(execution.startedAt ?? execution.createdAt)}
                      </time>
                    </p>
                  </div>
                  <StatusIndicator state={EXECUTION_STATUS_TO_STATUS[execution.status]} />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <p className="text-muted-foreground text-sm">
        {executions.length} execution{executions.length === 1 ? "" : "s"}
      </p>
    </div>
  );
}
