"use client";

import Link from "next/link";

import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { useInventoryStatistics } from "@/features/infrastructure/hooks/use-statistics";

/**
 * Infrastructure Overview (§18) — the same `useInventoryStatistics`
 * query `AssetHealthSection` already reads (React Query dedupes: one
 * request serves both widgets, §36). Deliberately does NOT repeat a
 * total-asset-count tile: `KpiGrid`'s own "Assets" tile already shows
 * that (from `OrganizationStatistics.assetCount`) — a second "Assets"
 * card here, sourced from a different backend computation
 * (`InventoryStatistics.totalAssets`), would risk showing two
 * differently-worded counts for what looks like the same thing (§43:
 * avoid redundant cards). This widget's own, non-duplicated value is
 * `totalRelationships`.
 *
 * No org-wide Topology summary/health endpoint exists (§19):
 * `topologyApi.get` (`GET /inventory/{assetId}/topology`) requires a
 * specific `assetId` — confirmed absent by direct source inspection,
 * see `docs/frontend/developer-guide/dashboard.md`. The one honest,
 * real, org-wide topology-adjacent number this backend does provide,
 * `totalRelationships`, is shown here rather than as its own thin
 * "Topology" card — with a direct link into the real per-asset
 * Topology experience (Prompt 018).
 */
export function InfrastructureOverviewWidget({ organizationId }: { organizationId: string }) {
  const query = useInventoryStatistics(organizationId);

  return (
    <DashboardWidget
      title="Infrastructure"
      description="Inventory size and relationships."
      action={{ label: "View Infrastructure", href: "/infrastructure" }}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
    >
      {query.data && (
        <div className="flex flex-col gap-3">
          <MetricCard label="Relationships" value={query.data.totalRelationships} />
          <Link href="/infrastructure/topology" className="text-primary text-xs font-medium hover:underline">
            Open Topology
          </Link>
        </div>
      )}
    </DashboardWidget>
  );
}
