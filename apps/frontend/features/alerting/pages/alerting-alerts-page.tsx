"use client";

import { RefreshCw } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AlertFilters, EMPTY_ALERT_FILTERS, type AlertFilterValues } from "@/features/alerting/components/alert-filters";
import { AlertingSubNav } from "@/features/alerting/components/alerting-sub-nav";
import { AlertTable, type AlertSortField } from "@/features/alerting/components/alert-table";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { SEVERITY_RANK } from "@/features/alerting/lib/severity";
import type { Alert, AlertSeverity, AlertStatusValue } from "@/features/alerting/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const DEFAULT_SORT_FIELD: AlertSortField = "triggeredAt";

function hasActiveFilters(filters: AlertFilterValues): boolean {
  return Boolean(filters.query || filters.status || filters.severity);
}

function matchesQuery(alert: Alert, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return (
    alert.title.toLowerCase().includes(needle) ||
    alert.message.toLowerCase().includes(needle) ||
    alert.source.toLowerCase().includes(needle)
  );
}

function compareAlerts(a: Alert, b: Alert, field: AlertSortField): number {
  switch (field) {
    case "severity":
      return SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
    case "triggeredAt":
      return new Date(a.triggeredAt).getTime() - new Date(b.triggeredAt).getTime();
    default:
      return a[field].localeCompare(b[field]);
  }
}

/**
 * Every alert for this organization (§9, Level 2). `status`/`severity`
 * are real `GET /alerts` params; `query` (search) and sort are applied
 * client-side over that endpoint's full, unpaginated result — honest
 * because nothing is hidden behind a page boundary the client can't
 * see (§24, §6). Filter/sort state lives in the URL (§14) so the view
 * is shareable and survives navigation.
 */
export function AlertingAlertsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const filters: AlertFilterValues = useMemo(
    () => ({
      query: searchParams.get("q") ?? EMPTY_ALERT_FILTERS.query,
      status: (searchParams.get("status") as AlertStatusValue | null) ?? EMPTY_ALERT_FILTERS.status,
      severity: (searchParams.get("severity") as AlertSeverity | null) ?? EMPTY_ALERT_FILTERS.severity,
    }),
    [searchParams],
  );
  const sortField = (searchParams.get("sort") as AlertSortField | null) ?? DEFAULT_SORT_FIELD;
  const sortDirection = searchParams.get("dir") === "asc" ? "asc" : "desc";

  const updateParams = useCallback(
    (next: Partial<{ q: string; status: string; severity: string; sort: string; dir: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/alerting/alerts?${params.toString()}`);
    },
    [router, searchParams],
  );

  const query = useAlerts(
    selectedOrganizationId
      ? { organizationId: selectedOrganizationId, status: filters.status || undefined, severity: filters.severity || undefined }
      : null,
  );

  const visibleAlerts = useMemo(() => {
    if (!query.data) return [];
    const filtered = query.data.filter((alert) => matchesQuery(alert, filters.query));
    const sorted = [...filtered].sort((a, b) => compareAlerts(a, b, sortField));
    return sortDirection === "asc" ? sorted : sorted.reverse();
  }, [query.data, filters.query, sortField, sortDirection]);

  function handleFiltersChange(next: AlertFilterValues) {
    updateParams({ q: next.query, status: next.status, severity: next.severity });
  }

  function handleReset() {
    updateParams({ q: "", status: "", severity: "" });
  }

  function handleSortChange(field: AlertSortField) {
    const nextDirection = sortField === field && sortDirection === "asc" ? "desc" : "asc";
    updateParams({ sort: field, dir: nextDirection });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Alerts"
        description="Every alert for this organization, filterable and searchable."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh alerts" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <AlertingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <AlertFilters values={filters} onChange={handleFiltersChange} onReset={handleReset} />
            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (visibleAlerts.length === 0 ? (
                  <EmptyState
                    title={hasActiveFilters(filters) ? "No matching alerts" : "No alerts yet"}
                    description={
                      hasActiveFilters(filters)
                        ? "Try a different search term or clear filters."
                        : "Nothing has been raised for this organization yet."
                    }
                  />
                ) : (
                  <AlertTable alerts={visibleAlerts} sortField={sortField} sortDirection={sortDirection} onSortChange={handleSortChange} />
                ))}
            </SectionState>
          </div>
        )}
      </SectionState>
    </div>
  );
}
