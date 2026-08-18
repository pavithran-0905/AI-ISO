"use client";

import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/components/navigation/page-header";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { FavoriteReportsList } from "@/features/reporting/components/favorite-reports-list";
import { RecentGenerationsList } from "@/features/reporting/components/recent-generations-list";
import { ReportingSubNav } from "@/features/reporting/components/reporting-sub-nav";
import { ReportingSummary } from "@/features/reporting/components/reporting-summary";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Reporting Overview (§4) — real report/generation/schedule counts,
 * recent activity, and this user's own favorites. Mirrors Monitoring's
 * and Alerting's overview structure (sub-nav + summary sections),
 * reusing the same organization-selection foundation.
 */
export function ReportingOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Reporting"
        description="Report design, scheduling, export, and distribution."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh reporting data" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <ReportingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Summary</SectionHeading>
              <ReportingSummary organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <section>
                <SectionHeading>Recent generations</SectionHeading>
                <RecentGenerationsList organizationId={selectedOrganizationId} />
              </section>

              <section>
                <SectionHeading>Favorites</SectionHeading>
                <FavoriteReportsList organizationId={selectedOrganizationId} />
              </section>
            </div>
          </div>
        )}
      </SectionState>
    </div>
  );
}
