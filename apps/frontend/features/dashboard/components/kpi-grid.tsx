"use client";

import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useOrganizationStatistics } from "@/features/dashboard/hooks/use-organization-statistics";

/**
 * Executive summary KPIs (§6/§7) — every value comes straight from
 * `GET /organizations/{id}/analytics`'s `OrganizationStatisticsResponse`,
 * a real snapshot count, never estimated. No trend/percentage-change is
 * shown (§7 forbids fabricating one without real historical data).
 */
export function KpiGrid({ organizationId }: { organizationId: string }) {
  const query = useOrganizationStatistics(organizationId);

  return (
    <SectionState
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-24 w-full"
    >
      {query.data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Users" value={query.data.userCount} />
          <MetricCard label="Projects" value={query.data.projectCount} />
          <MetricCard label="Assets" value={query.data.assetCount} href="/monitoring/assets" />
          <MetricCard label="Workflows" value={query.data.workflowCount} />
          <MetricCard label="Automations" value={query.data.automationCount} />
          <MetricCard label="Validations" value={query.data.validationCount} />
        </div>
      )}
    </SectionState>
  );
}
