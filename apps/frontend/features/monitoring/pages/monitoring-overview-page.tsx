"use client";

import { RefreshCw } from "lucide-react";

import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { CriticalIssuesSection } from "@/features/monitoring/components/critical-issues-section";
import { EventTimeline } from "@/features/monitoring/components/event-timeline";
import { HealthSummary } from "@/features/monitoring/components/health-summary";
import { MonitoringSubNav } from "@/features/monitoring/components/monitoring-sub-nav";
import { ServiceHealthList } from "@/features/monitoring/components/service-health-list";
import { PageHeader } from "@/components/navigation/page-header";
import { IconButton } from "@/components/ui/icon-button";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Monitoring Overview (§4) — answers "what's healthy / degraded /
 * failed / changed recently / needs investigation" from real V1 data.
 * Reuses the same organization selection as the Dashboard
 * (`@/organization`) rather than prompting again per page.
 */
export function MonitoringOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Monitoring"
        description="Infrastructure health, assets, services, and events."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh monitoring data" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <MonitoringSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Health summary</SectionHeading>
              <HealthSummary organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading>Critical issues</SectionHeading>
              <CriticalIssuesSection organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <section>
                <SectionHeading>Service health</SectionHeading>
                <ServiceHealthList limit={5} />
              </section>

              <section>
                <SectionHeading>Recent events</SectionHeading>
                <EventTimeline limit={5} />
              </section>
            </div>
          </div>
        )}
      </SectionState>
    </div>
  );
}
