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
import { ReportFilters, EMPTY_REPORT_FILTERS, type ReportFilterValues } from "@/features/reporting/components/report-filters";
import { ReportingSubNav } from "@/features/reporting/components/reporting-sub-nav";
import { ReportTable, type ReportSortField } from "@/features/reporting/components/report-table";
import { useFavoriteReports, useReports, useToggleFavorite } from "@/features/reporting/hooks/use-reports";
import type { Report, ReportCategory } from "@/features/reporting/types";
import { usePermissions } from "@/permissions/hooks";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const DEFAULT_SORT_FIELD: ReportSortField = "name";

function hasActiveFilters(filters: ReportFilterValues): boolean {
  return Boolean(filters.query || filters.category || filters.enabledOnly);
}

function matchesQuery(report: Report, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return report.name.toLowerCase().includes(needle) || (report.description ?? "").toLowerCase().includes(needle);
}

function compareReports(a: Report, b: Report, field: ReportSortField): number {
  return a[field].localeCompare(b[field]);
}

/**
 * Every report for this organization (§5). `category`/`enabled_only`
 * are real `GET /reports` params; `query` (search) and sort are
 * applied client-side over that endpoint's full, unpaginated result —
 * honest because nothing is hidden behind a page boundary the client
 * can't see (§23).
 */
export function ReportsListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const { can } = usePermissions();

  const filters: ReportFilterValues = useMemo(
    () => ({
      query: searchParams.get("q") ?? EMPTY_REPORT_FILTERS.query,
      category: (searchParams.get("category") as ReportCategory | null) ?? EMPTY_REPORT_FILTERS.category,
      enabledOnly: searchParams.get("enabled") === "true",
    }),
    [searchParams],
  );
  const sortField = (searchParams.get("sort") as ReportSortField | null) ?? DEFAULT_SORT_FIELD;
  const sortDirection = searchParams.get("dir") === "desc" ? "desc" : "asc";

  const updateParams = useCallback(
    (next: Partial<{ q: string; category: string; enabled: string; sort: string; dir: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/reporting/reports?${params.toString()}`);
    },
    [router, searchParams],
  );

  const query = useReports(
    selectedOrganizationId
      ? { organizationId: selectedOrganizationId, category: filters.category || undefined, enabledOnly: filters.enabledOnly || undefined }
      : null,
  );
  const favoritesQuery = useFavoriteReports(selectedOrganizationId);
  const toggleFavorite = useToggleFavorite();

  const favoriteIds = useMemo(() => new Set((favoritesQuery.data ?? []).map((report) => report.id)), [favoritesQuery.data]);

  const visibleReports = useMemo(() => {
    if (!query.data) return [];
    const filtered = query.data.filter((report) => matchesQuery(report, filters.query));
    const sorted = [...filtered].sort((a, b) => compareReports(a, b, sortField));
    return sortDirection === "asc" ? sorted : sorted.reverse();
  }, [query.data, filters.query, sortField, sortDirection]);

  function handleFiltersChange(next: ReportFilterValues) {
    updateParams({ q: next.query, category: next.category, enabled: next.enabledOnly ? "true" : "" });
  }

  function handleReset() {
    updateParams({ q: "", category: "", enabled: "" });
  }

  function handleSortChange(field: ReportSortField) {
    const nextDirection = sortField === field && sortDirection === "asc" ? "desc" : "asc";
    updateParams({ sort: field, dir: nextDirection });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Reports"
        description="Every report saved for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <div className="flex items-center gap-2">
            <IconButton icon={RefreshCw} aria-label="Refresh reports" variant="outline" loading={isRefreshing} onClick={refresh} />
            {can("create") && (
              <Button onClick={() => router.push("/reporting/reports/new")} className="gap-1.5">
                <Plus className="size-4" aria-hidden="true" />
                New report
              </Button>
            )}
          </div>
        }
      />
      <ReportingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <ReportFilters values={filters} onChange={handleFiltersChange} onReset={handleReset} />
            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (visibleReports.length === 0 ? (
                  <EmptyState
                    title={hasActiveFilters(filters) ? "No matching reports" : "No reports yet"}
                    description={
                      hasActiveFilters(filters)
                        ? "Try a different search term or clear filters."
                        : can("create")
                          ? "Create your first report to get started."
                          : "Nothing has been created for this organization yet."
                    }
                    action={
                      !hasActiveFilters(filters) && can("create") ? (
                        <Link href="/reporting/reports/new" className="text-primary text-sm font-medium hover:underline">
                          New report
                        </Link>
                      ) : undefined
                    }
                  />
                ) : (
                  <ReportTable
                    reports={visibleReports}
                    favoriteIds={favoriteIds}
                    onToggleFavorite={(reportId, favorited) => toggleFavorite.mutate({ reportId, favorited })}
                    sortField={sortField}
                    sortDirection={sortDirection}
                    onSortChange={handleSortChange}
                  />
                ))}
            </SectionState>
          </div>
        )}
      </SectionState>
    </div>
  );
}
