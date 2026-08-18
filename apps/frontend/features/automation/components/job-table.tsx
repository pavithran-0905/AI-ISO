"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { JOB_STATUS_TONE } from "@/features/automation/lib/status-maps";
import type { AutomationJob } from "@/features/automation/types";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

export type JobSortField = "name" | "automationType" | "playbookType" | "status";

const COLUMNS: { field: JobSortField; label: string }[] = [
  { field: "name", label: "Automation" },
  { field: "automationType", label: "Type" },
  { field: "playbookType", label: "Playbook" },
  { field: "status", label: "Status" },
];

/**
 * The automations table (§5). Columns are exactly the real
 * `AutomationJobResponse` fields — deliberately **no** "Owner name",
 * "Last execution", "Next scheduled run", "Target", or "Updated"
 * columns, all of which §5 lists as possibilities: `owner_id` is a
 * bare UUID with no resolution endpoint, and the response carries no
 * timestamps, no last/next run, and no resolvable target at all
 * (confirmed by source inspection of the response mapper). See
 * `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function JobTable({
  jobs,
  sortField,
  sortDirection,
  onSortChange,
}: {
  jobs: AutomationJob[];
  sortField: JobSortField;
  sortDirection: "asc" | "desc";
  onSortChange: (field: JobSortField) => void;
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
            {jobs.map((job) => (
              <tr key={job.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                <td className={cellPadding}>
                  <Link
                    href={`/automation/automations/${job.id}`}
                    className="focus-visible:ring-ring rounded font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {job.name}
                  </Link>
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{job.automationType.replace(/_/g, " ")}</td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{job.playbookType.replace(/_/g, " ")}</td>
                <td className={cellPadding}>
                  <StatusBadge tone={JOB_STATUS_TONE[job.status]} label={job.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {jobs.map((job) => (
          <li key={job.id}>
            <Link href={`/automation/automations/${job.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-sm font-medium">{job.name}</p>
                    <p className="text-muted-foreground text-xs">{job.automationType.replace(/_/g, " ")}</p>
                  </div>
                  <StatusBadge tone={JOB_STATUS_TONE[job.status]} label={job.status} className="shrink-0" />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <p className="text-muted-foreground text-sm">
        {jobs.length} automation{jobs.length === 1 ? "" : "s"}
      </p>
    </div>
  );
}
