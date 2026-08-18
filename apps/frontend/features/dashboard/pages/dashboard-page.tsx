"use client";

import { RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

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
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
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
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>(() => new Date().toISOString());

  async function handleRefresh() {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    setLastRefreshedAt(new Date().toISOString());
    setIsRefreshing(false);
  }

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
            onClick={handleRefresh}
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
              <SectionHeading>Operational health</SectionHeading>
              <HealthOverviewSection organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <section>
                <SectionHeading>Attention required</SectionHeading>
                <AttentionRequiredSection organizationId={selectedOrganizationId} />
              </section>

              <section>
                <SectionHeading>Recent automation activity</SectionHeading>
                <RecentActivitySection organizationId={selectedOrganizationId} />
              </section>
            </div>

            <section>
              <SectionHeading>System status</SectionHeading>
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
