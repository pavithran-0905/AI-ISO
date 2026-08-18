"use client";

import { Download, History, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { StatusBadge } from "@/components/feedback/status-badge";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ArchiveFilters, EMPTY_ARCHIVE_FILTERS, type ArchiveFilterValues } from "@/features/reporting/components/archive-filters";
import { PurgeArchiveDialog } from "@/features/reporting/components/purge-archive-dialog";
import { ReportingSubNav } from "@/features/reporting/components/reporting-sub-nav";
import { useArchivedReports, useDownloadArchive, useRestoreArchive } from "@/features/reporting/hooks/use-archive";
import { formatBytes } from "@/features/reporting/lib/format-duration";
import { ARCHIVE_STATUS_TONE } from "@/features/reporting/lib/status-tones";
import type { ArchivedReport } from "@/features/reporting/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { usePermissions } from "@/permissions/hooks";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

/**
 * Archive (§19/§20) — real immutable copies of generated reports.
 * `status`/`search` are real server-side `GET /reports/archive` params.
 * Purge is gated by the backend's own retention policy — see
 * `PurgeArchiveDialog`'s own docstring for why a rejected purge shows
 * the backend's real reason rather than a generic failure.
 */
export function ArchiveListPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const { can } = usePermissions();
  const [filters, setFilters] = useState<ArchiveFilterValues>(EMPTY_ARCHIVE_FILTERS);
  const [purgeTarget, setPurgeTarget] = useState<ArchivedReport | null>(null);

  const query = useArchivedReports(selectedOrganizationId, { search: filters.search || undefined, status: filters.status || undefined });
  const download = useDownloadArchive();
  const restore = useRestoreArchive();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Archive"
        description="Immutable, retention-governed copies of generated reports."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={<IconButton icon={RefreshCw} aria-label="Refresh archive" variant="outline" loading={isRefreshing} onClick={refresh} />}
      />
      <ReportingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <ArchiveFilters values={filters} onChange={setFilters} onReset={() => setFilters(EMPTY_ARCHIVE_FILTERS)} />
            <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
              {query.data &&
                (query.data.length === 0 ? (
                  <EmptyState title="No archived reports match your filters" description="Archive a generation from its report's detail page." />
                ) : (
                  <ul className="flex flex-col gap-2">
                    {query.data.map((archived) => (
                      <li key={archived.id}>
                        <Card>
                          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-3">
                            <div className="flex flex-col gap-0.5">
                              <p className="text-sm font-medium">
                                {archived.title} <span className="text-muted-foreground font-normal">v{archived.archiveVersion}</span>
                              </p>
                              <p className="text-muted-foreground text-xs">
                                {archived.exportFormat.toUpperCase()} · {formatBytes(archived.sizeBytes)} ·{" "}
                                <time dateTime={archived.archivedAt}>{formatRelativeTime(archived.archivedAt)}</time>
                                {archived.retentionUntil && (
                                  <>
                                    {" "}
                                    · retained until <time dateTime={archived.retentionUntil}>{new Date(archived.retentionUntil).toLocaleDateString()}</time>
                                  </>
                                )}
                              </p>
                              {archived.purgeReason && <p className="text-muted-foreground text-xs">Purge reason: {archived.purgeReason}</p>}
                            </div>
                            <div className="flex items-center gap-2">
                              <StatusBadge tone={ARCHIVE_STATUS_TONE[archived.status]} label={archived.status} />
                              {archived.status === "active" && (
                                <>
                                  <Button
                                    variant="outline"
                                    onClick={() => download.mutate({ archiveId: archived.id, filename: archived.filename })}
                                    loading={download.isPending && download.variables?.archiveId === archived.id}
                                    className="gap-1.5"
                                  >
                                    <Download className="size-4" aria-hidden="true" />
                                    Download
                                  </Button>
                                  {can("update") && (
                                    <IconButton
                                      icon={History}
                                      aria-label="Restore as a new export"
                                      variant="outline"
                                      onClick={() => restore.mutate(archived.id)}
                                      loading={restore.isPending && restore.variables === archived.id}
                                    />
                                  )}
                                  {can("delete") && (
                                    <IconButton icon={Trash2} aria-label="Purge" variant="outline" onClick={() => setPurgeTarget(archived)} />
                                  )}
                                </>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </li>
                    ))}
                  </ul>
                ))}
            </SectionState>
          </div>
        )}
      </SectionState>

      {purgeTarget && (
        <PurgeArchiveDialog archiveId={purgeTarget.id} title={purgeTarget.title} open={purgeTarget !== null} onClose={() => setPurgeTarget(null)} />
      )}
    </div>
  );
}
