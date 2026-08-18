"use client";

import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/components/navigation/page-header";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { RecentGenerationsList } from "@/features/reporting/components/recent-generations-list";
import { ReportingSubNav } from "@/features/reporting/components/reporting-sub-nav";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const HISTORY_LIMIT = 100;

/** Every generation event across every report in this organization
 * (§14) — `GET /reports/history` with no `report_id` filter, capped at
 * the endpoint's own maximum (`limit<=1000`; a reasonable 100 is used
 * here). */
export function HistoryListPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Generated Reports"
        description="Every report generation event recorded for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={<IconButton icon={RefreshCw} aria-label="Refresh generated reports" variant="outline" loading={isRefreshing} onClick={refresh} />}
      />
      <ReportingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && <RecentGenerationsList organizationId={selectedOrganizationId} limit={HISTORY_LIMIT} />}
      </SectionState>
    </div>
  );
}
