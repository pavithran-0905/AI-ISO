"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useInventoryAnalytics } from "@/features/infrastructure/hooks/use-statistics";
import { formatRelativeTime } from "@/lib/relative-time";

function DistributionCard({ title, distribution }: { title: string; distribution: Record<string, number> }) {
  const entries = Object.entries(distribution).sort(([, a], [, b]) => b - a);
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 p-4">
        <p className="text-sm font-medium">{title}</p>
        {entries.length === 0 ? (
          <p className="text-muted-foreground text-xs">No data yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {entries.slice(0, 6).map(([key, count]) => (
              <li key={key} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-muted-foreground truncate">{key}</span>
                <span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * `GET /inventory/analytics` (§5) — real, backend-computed
 * distributions, never derived by fetching and counting assets
 * client-side. No fabricated "Machines"/"Services" categories: V1 has
 * 44 individual `asset_type` values and no grouping concept of its own
 * (confirmed absent), so the real per-type breakdown is shown as-is
 * rather than an invented aggregation.
 */
export function InfrastructureStatisticsSummary({ organizationId }: { organizationId: string }) {
  const query = useInventoryAnalytics(organizationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data && (
        <div className="flex flex-col gap-4">
          <p className="text-muted-foreground text-xs">
            Computed <time dateTime={query.data.computedAt}>{formatRelativeTime(query.data.computedAt)}</time>
          </p>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard label="Total assets" value={query.data.totalAssets} href="/infrastructure/assets" />
            <MetricCard label="Relationships" value={query.data.totalRelationships} />
            <MetricCard label="Added in last 30 days" value={query.data.assetsAddedLast30Days} />
            <MetricCard label="Unclassified type" value={query.data.typeDistribution.custom_asset ?? 0} />
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <DistributionCard title="By type" distribution={query.data.typeDistribution} />
            <DistributionCard title="By health" distribution={query.data.healthDistribution} />
            <DistributionCard title="By lifecycle" distribution={query.data.lifecycleDistribution} />
            <DistributionCard title="By operating system" distribution={query.data.osDistribution} />
            <DistributionCard title="By vendor" distribution={query.data.vendorDistribution} />
            <DistributionCard title="By discovery source" distribution={query.data.discoverySourceDistribution} />
          </div>
        </div>
      )}
    </SectionState>
  );
}
