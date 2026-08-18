"use client";

import { RefreshCw, Search, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AutomationSubNav } from "@/features/automation/components/automation-sub-nav";
import { ExecutionTable, type ExecutionSortField } from "@/features/automation/components/execution-table";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import { useAutomationJobs } from "@/features/automation/hooks/use-jobs";
import { executionDurationMs } from "@/features/automation/lib/duration";
import { EXECUTION_STATUSES, type ExecutionStatusValue } from "@/features/automation/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const DEFAULT_SORT_FIELD: ExecutionSortField = "createdAt";

/**
 * Execution history (§7/§21). `status` is a real server-side
 * `GET /automation/executions` parameter; the job filter and sort are
 * applied client-side over the endpoint's complete, unpaginated
 * result. There is no date-range filter — §21 lists one, but the
 * endpoint has no such param and adding a client-side one over an
 * unbounded list would be misleading about what it filters.
 */
export function ExecutionsListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const status = (searchParams.get("status") as ExecutionStatusValue | null) ?? "";
  const jobId = searchParams.get("job") ?? "";
  const sortField = (searchParams.get("sort") as ExecutionSortField | null) ?? DEFAULT_SORT_FIELD;
  const sortDirection = searchParams.get("dir") === "asc" ? "asc" : "desc";

  const updateParams = useCallback(
    (next: Partial<{ status: string; job: string; sort: string; dir: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/automation/executions?${params.toString()}`);
    },
    [router, searchParams],
  );

  const query = useExecutions(
    selectedOrganizationId ? { organizationId: selectedOrganizationId, status: status || undefined } : null,
  );
  const jobsQuery = useAutomationJobs(selectedOrganizationId);

  const jobNameById = useMemo(() => new Map((jobsQuery.data ?? []).map((job) => [job.id, job.name])), [jobsQuery.data]);

  const visibleExecutions = useMemo(() => {
    if (!query.data) return [];
    const filtered = jobId ? query.data.filter((execution) => execution.jobId === jobId) : query.data;
    const sorted = [...filtered].sort((a, b) => {
      if (sortField === "status") return a.status.localeCompare(b.status);
      if (sortField === "duration") return (executionDurationMs(a) ?? 0) - (executionDurationMs(b) ?? 0);
      return new Date(a.startedAt ?? a.createdAt).getTime() - new Date(b.startedAt ?? b.createdAt).getTime();
    });
    return sortDirection === "asc" ? sorted : sorted.reverse();
  }, [query.data, jobId, sortField, sortDirection]);

  const activeFilterCount = [status, jobId].filter(Boolean).length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Executions"
        description="Every automation run recorded for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={<IconButton icon={RefreshCw} aria-label="Refresh executions" variant="outline" loading={isRefreshing} onClick={refresh} />}
      />
      <AutomationSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="execution-status-filter">Status</Label>
                <Select
                  id="execution-status-filter"
                  value={status}
                  onChange={(event) => updateParams({ status: event.target.value })}
                  className="w-40"
                >
                  <option value="">All statuses</option>
                  {EXECUTION_STATUSES.map((value) => (
                    <option key={value} value={value}>
                      {value.replace(/_/g, " ")}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex min-w-56 flex-col gap-1.5">
                <Label htmlFor="execution-job-filter">Automation</Label>
                <div className="relative">
                  <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
                  <Select
                    id="execution-job-filter"
                    value={jobId}
                    onChange={(event) => updateParams({ job: event.target.value })}
                    className="pl-9"
                  >
                    <option value="">All automations</option>
                    {(jobsQuery.data ?? []).map((job) => (
                      <option key={job.id} value={job.id}>
                        {job.name}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
              {activeFilterCount > 0 && (
                <Button variant="ghost" onClick={() => updateParams({ status: "", job: "" })} className="gap-1.5">
                  <X className="size-4" aria-hidden="true" />
                  Reset
                  <Badge variant="outline">{activeFilterCount}</Badge>
                </Button>
              )}
            </div>

            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (visibleExecutions.length === 0 ? (
                  <EmptyState
                    title="No executions found"
                    description={activeFilterCount > 0 ? "Try clearing the filters." : "Nothing has been run for this organization yet."}
                  />
                ) : (
                  <ExecutionTable
                    executions={visibleExecutions}
                    jobNameById={jobNameById}
                    sortField={sortField}
                    sortDirection={sortDirection}
                    onSortChange={(field) =>
                      updateParams({ sort: field, dir: sortField === field && sortDirection === "asc" ? "desc" : "asc" })
                    }
                  />
                ))}
            </SectionState>
          </div>
        )}
      </SectionState>
    </div>
  );
}
