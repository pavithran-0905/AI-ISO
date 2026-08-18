"use client";

import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/components/navigation/page-header";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AlertingSubNav } from "@/features/alerting/components/alerting-sub-nav";
import { AlertSummary } from "@/features/alerting/components/alert-summary";
import { MaintenanceWindowsList } from "@/features/alerting/components/maintenance-windows-list";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Alerting Overview (§9, Level 1) — mirrors Monitoring's overview
 * structure (sub-nav + summary sections), reusing the same
 * organization-selection foundation as Dashboard and Monitoring.
 */
export function AlertingOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Alerting"
        description="Active alerts, severity, acknowledgement, and resolution."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh alerting data" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <AlertingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Summary</SectionHeading>
              <AlertSummary organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading>Active maintenance windows</SectionHeading>
              <MaintenanceWindowsList organizationId={selectedOrganizationId} />
            </section>
          </div>
        )}
      </SectionState>
    </div>
  );
}
