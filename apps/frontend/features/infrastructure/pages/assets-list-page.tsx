"use client";

import { Download, Plus, RefreshCw, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { buttonVariants } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { AssetFilters, EMPTY_FILTERS, type AssetFilterValues } from "@/features/infrastructure/components/asset-filters";
import { AssetTable, type AssetSortField } from "@/features/infrastructure/components/asset-table";
import { ExportDialog } from "@/features/infrastructure/components/export-dialog";
import { ImportDialog } from "@/features/infrastructure/components/import-dialog";
import { InfrastructureSubNav } from "@/features/infrastructure/components/infrastructure-sub-nav";
import { useAssetSearch } from "@/features/infrastructure/hooks/use-assets";
import type { AssetStatusValue, AssetTypeValue } from "@/features/infrastructure/types";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { usePermissions } from "@/permissions/hooks";
import { useSelectedOrganization } from "@/organization/use-organizations";

const DEFAULT_SORT_FIELD: AssetSortField = "updated_at";
const PAGE_SIZE = 25;

function hasActiveFilters(filters: AssetFilterValues): boolean {
  return Boolean(filters.query || filters.status || filters.assetType);
}

/**
 * The Assets table (§6) — filters, search, sort, and pagination are
 * all real `GET /inventory/search` query params, kept in the URL so
 * the exact view is shareable/bookmarkable and survives back/forward
 * navigation (§18/§19/§20).
 */
export function AssetsListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { can } = usePermissions();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const [exportOpen, setExportOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const filters: AssetFilterValues = useMemo(
    () => ({
      query: searchParams.get("q") ?? EMPTY_FILTERS.query,
      status: (searchParams.get("status") as AssetStatusValue | null) ?? EMPTY_FILTERS.status,
      assetType: (searchParams.get("type") as AssetTypeValue | null) ?? EMPTY_FILTERS.assetType,
    }),
    [searchParams],
  );
  const page = Number(searchParams.get("page") ?? "1") || 1;
  const sortField = (searchParams.get("sort") as AssetSortField | null) ?? DEFAULT_SORT_FIELD;
  const sortDirection = searchParams.get("dir") === "asc" ? "asc" : "desc";

  const updateParams = useCallback(
    (next: Partial<{ q: string; status: string; type: string; page: string; sort: string; dir: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/infrastructure/assets?${params.toString()}`);
    },
    [router, searchParams],
  );

  const query = useAssetSearch(
    selectedOrganizationId
      ? {
          organizationId: selectedOrganizationId,
          query: filters.query || undefined,
          status: filters.status || undefined,
          assetType: filters.assetType || undefined,
          page,
          pageSize: PAGE_SIZE,
          sort: `${sortField}:${sortDirection}`,
        }
      : null,
  );

  function handleFiltersChange(next: AssetFilterValues) {
    updateParams({ q: next.query, status: next.status, type: next.assetType, page: "" });
  }

  function handleReset() {
    updateParams({ q: "", status: "", type: "", page: "" });
  }

  function handleSortChange(field: AssetSortField) {
    const nextDirection = sortField === field && sortDirection === "asc" ? "desc" : "asc";
    updateParams({ sort: field, dir: nextDirection, page: "" });
  }

  function handlePageChange(nextPage: number) {
    updateParams({ page: String(nextPage) });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Assets"
        description="Every asset registered for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <div className="flex items-center gap-2">
            {can("export") && (
              <IconButton icon={Download} aria-label="Export assets" variant="outline" onClick={() => setExportOpen(true)} />
            )}
            {can("import") && (
              <IconButton icon={Upload} aria-label="Import assets" variant="outline" onClick={() => setImportOpen(true)} />
            )}
            <IconButton icon={RefreshCw} aria-label="Refresh assets" variant="outline" loading={isRefreshing} onClick={refresh} />
            {can("create") && (
              <Link href="/infrastructure/assets/new" className={buttonVariants("primary", "gap-1.5")}>
                <Plus className="size-4" aria-hidden="true" />
                New asset
              </Link>
            )}
          </div>
        }
      />
      <InfrastructureSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <AssetFilters values={filters} onChange={handleFiltersChange} onReset={handleReset} />
            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (query.data.items.length === 0 ? (
                  <EmptyState
                    title={hasActiveFilters(filters) ? "No matching assets" : "No assets yet"}
                    description={
                      hasActiveFilters(filters)
                        ? "Try a different search term or clear filters."
                        : "Nothing has been discovered or registered for this organization yet."
                    }
                    action={
                      !hasActiveFilters(filters) && can("create") ? (
                        <Link href="/infrastructure/assets/new" className={buttonVariants("outline")}>
                          Register an asset
                        </Link>
                      ) : undefined
                    }
                  />
                ) : (
                  <AssetTable
                    assets={query.data.items}
                    pagination={query.data.pagination}
                    sortField={sortField}
                    sortDirection={sortDirection}
                    onSortChange={handleSortChange}
                    onPageChange={handlePageChange}
                  />
                ))}
            </SectionState>

            {selectedOrganizationId && (
              <>
                <ExportDialog organizationId={selectedOrganizationId} open={exportOpen} onClose={() => setExportOpen(false)} />
                <ImportDialog organizationId={selectedOrganizationId} open={importOpen} onClose={() => setImportOpen(false)} />
              </>
            )}
          </div>
        )}
      </SectionState>
    </div>
  );
}
