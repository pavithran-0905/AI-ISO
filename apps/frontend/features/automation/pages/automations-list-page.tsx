"use client";

import { Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AutomationSubNav } from "@/features/automation/components/automation-sub-nav";
import { EMPTY_JOB_FILTERS, JobFilters, type JobFilterValues } from "@/features/automation/components/job-filters";
import { JobTable, type JobSortField } from "@/features/automation/components/job-table";
import { useAutomationJobs } from "@/features/automation/hooks/use-jobs";
import type { AutomationJob, AutomationTypeValue, JobStatusValue } from "@/features/automation/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { usePermissions } from "@/permissions/hooks";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const DEFAULT_SORT_FIELD: JobSortField = "name";

function hasActiveFilters(filters: JobFilterValues): boolean {
  return Boolean(filters.query || filters.status || filters.automationType);
}

function matchesQuery(job: AutomationJob, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return (
    job.name.toLowerCase().includes(needle) ||
    (job.description ?? "").toLowerCase().includes(needle) ||
    job.tags.some((tag) => tag.toLowerCase().includes(needle))
  );
}

/**
 * Every automation for this organization (§5). Search, filtering, and
 * sorting are all client-side because `GET /automation/jobs` accepts
 * no such params — but it returns the organization's complete job list
 * unpaginated, so nothing is hidden behind a page boundary. Filter and
 * sort state lives in the URL so a specific view is shareable.
 *
 * There is deliberately no pagination control (§5 lists it): with no
 * server-side paging available, adding client-side pages would only
 * hide rows the browser already has.
 */
export function AutomationsListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const { can } = usePermissions();

  const filters: JobFilterValues = useMemo(
    () => ({
      query: searchParams.get("q") ?? EMPTY_JOB_FILTERS.query,
      status: (searchParams.get("status") as JobStatusValue | null) ?? EMPTY_JOB_FILTERS.status,
      automationType: (searchParams.get("type") as AutomationTypeValue | null) ?? EMPTY_JOB_FILTERS.automationType,
    }),
    [searchParams],
  );
  const sortField = (searchParams.get("sort") as JobSortField | null) ?? DEFAULT_SORT_FIELD;
  const sortDirection = searchParams.get("dir") === "desc" ? "desc" : "asc";

  const updateParams = useCallback(
    (next: Partial<{ q: string; status: string; type: string; sort: string; dir: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/automation/automations?${params.toString()}`);
    },
    [router, searchParams],
  );

  const query = useAutomationJobs(selectedOrganizationId);

  const visibleJobs = useMemo(() => {
    if (!query.data) return [];
    const filtered = query.data.filter(
      (job) =>
        matchesQuery(job, filters.query) &&
        (!filters.status || job.status === filters.status) &&
        (!filters.automationType || job.automationType === filters.automationType),
    );
    const sorted = [...filtered].sort((a, b) => a[sortField].localeCompare(b[sortField]));
    return sortDirection === "asc" ? sorted : sorted.reverse();
  }, [query.data, filters, sortField, sortDirection]);

  function handleSortChange(field: JobSortField) {
    const nextDirection = sortField === field && sortDirection === "asc" ? "desc" : "asc";
    updateParams({ sort: field, dir: nextDirection });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Automations"
        description="Every automation job defined for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <div className="flex items-center gap-2">
            <IconButton icon={RefreshCw} aria-label="Refresh automations" variant="outline" loading={isRefreshing} onClick={refresh} />
            {can("create") && (
              <Button onClick={() => router.push("/automation/automations/new")} className="gap-1.5">
                <Plus className="size-4" aria-hidden="true" />
                New automation
              </Button>
            )}
          </div>
        }
      />
      <AutomationSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <JobFilters
              values={filters}
              onChange={(next) => updateParams({ q: next.query, status: next.status, type: next.automationType })}
              onReset={() => updateParams({ q: "", status: "", type: "" })}
            />
            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (visibleJobs.length === 0 ? (
                  <EmptyState
                    title={hasActiveFilters(filters) ? "No matching automations" : "No automations configured"}
                    description={
                      hasActiveFilters(filters)
                        ? "Try a different search term or clear filters."
                        : can("create")
                          ? "Create your first automation to get started."
                          : "Nothing has been configured for this organization yet."
                    }
                    action={
                      !hasActiveFilters(filters) && can("create") ? (
                        <Link href="/automation/automations/new" className="text-primary text-sm font-medium hover:underline">
                          New automation
                        </Link>
                      ) : undefined
                    }
                  />
                ) : (
                  <JobTable jobs={visibleJobs} sortField={sortField} sortDirection={sortDirection} onSortChange={handleSortChange} />
                ))}
            </SectionState>
          </div>
        )}
      </SectionState>
    </div>
  );
}
