"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";

import { IconButton } from "@/components/ui/icon-button";
import { PageHeader } from "@/components/navigation/page-header";
import { AttentionRequiredSection } from "@/features/dashboard/components/attention-required-section";
import { GatewayLivenessCard } from "@/features/dashboard/components/gateway-liveness-card";
import { HealthOverviewSection } from "@/features/dashboard/components/health-overview-section";
import { KpiGrid } from "@/features/dashboard/components/kpi-grid";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { RecentActivitySection } from "@/features/dashboard/components/recent-activity-section";
import { SectionState } from "@/features/dashboard/components/section-state";
import { SystemStatusSection } from "@/features/dashboard/components/system-status-section";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `viewAllHref` only ever points at a route registered as
 * `"implemented"` in `lib/route-registry.ts` (§26: "only link to
 * routes that actually exist") — Monitoring (Prompt 006) and Alerting
 * (Prompt 007) shipped, so these sections finally have somewhere real
 * to send the operator for the fuller view. */
function SectionHeading({
  children,
  viewAllHref,
  viewAllLabel,
}: {
  children: React.ReactNode;
  viewAllHref?: string;
  viewAllLabel?: string;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className={typography.cardTitle}>{children}</h2>
      {viewAllHref && (
        <Link href={viewAllHref} className="text-primary text-xs font-medium hover:underline">
          {viewAllLabel ?? "View in Monitoring"}
        </Link>
      )}
    </div>
  );
}

export function DashboardPage() {
  const {
    organizations,
    isLoading: organizationsLoading,
    isError: organizationsError,
    selectedOrganizationId,
    needsSelection,
    hasNoAccess,
  } = useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        description="Platform overview and operational health."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton
            icon={RefreshCw}
            aria-label="Refresh dashboard"
            variant="outline"
            loading={isRefreshing}
            onClick={refresh}
          />
        }
      />

      <SectionState
        isLoading={organizationsLoading}
        isError={organizationsError}
        skeletonClassName="h-24 w-full"
      >
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Overview</SectionHeading>
              <KpiGrid organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading viewAllHref="/monitoring">Operational health</SectionHeading>
              <HealthOverviewSection organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <section>
                <SectionHeading viewAllHref="/alerting/alerts" viewAllLabel="View in Alerting">
                  Attention required
                </SectionHeading>
                <AttentionRequiredSection organizationId={selectedOrganizationId} />
              </section>

              <section>
                <SectionHeading viewAllHref="/automation/executions" viewAllLabel="View in Automation">
                  Recent automation activity
                </SectionHeading>
                <RecentActivitySection organizationId={selectedOrganizationId} />
              </section>
            </div>

            <section>
              <SectionHeading viewAllHref="/monitoring/services">System status</SectionHeading>
              <SystemStatusSection organizationId={selectedOrganizationId} />
            </section>
          </div>
        )}
      </SectionState>

      <div className="max-w-xs">
        <GatewayLivenessCard />
      </div>
    </div>
  );
}
