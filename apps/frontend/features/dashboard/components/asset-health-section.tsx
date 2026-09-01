"use client";

import { EmptyState } from "@/components/feedback/empty-state";
import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";
import { DistributionBar } from "@/features/dashboard/components/distribution-bar";
import { buildHealthSegments } from "@/features/dashboard/lib/asset-health";
import { useInventoryStatistics } from "@/features/infrastructure/hooks/use-statistics";

/**
 * Asset Health (§10/§11) — the top of the status hierarchy §9 itself
 * spells out ("Dashboard should prioritize: Asset health... Raw
 * validation counts belong in the relevant detail experience," i.e.
 * never "Total Checks" as the headline metric). Sourced from
 * `InventoryStatistics.healthDistribution` (`GET /inventory/statistics`)
 * — the same query `InfrastructureOverviewWidget` reads; React Query
 * dedupes identical `queryKey`s, so this is one request serving both
 * widgets (§36), not two. Always on in both dashboard modes — see
 * `dashboard-page.tsx`'s own comment on why this section isn't part of
 * the optional widget registry.
 */
export function AssetHealthSection({ organizationId }: { organizationId: string }) {
  const query = useInventoryStatistics(organizationId);

  return (
    <DashboardWidget
      title="Asset health"
      description="Current health of every registered asset."
      action={{ label: "View Infrastructure", href: "/infrastructure/assets" }}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-16 w-full"
    >
      {query.data &&
        (query.data.totalAssets === 0 ? (
          <EmptyState title="No assets registered yet" description="Register assets in Infrastructure to see health here." />
        ) : (
          <DistributionBar segments={buildHealthSegments(query.data.healthDistribution)} />
        ))}
    </DashboardWidget>
  );
}
