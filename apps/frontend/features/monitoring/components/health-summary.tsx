"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useInventoryStatistics } from "@/features/monitoring/hooks/use-inventory-statistics";
import { ASSET_HEALTH_STATUSES, type AssetHealthValue } from "@/features/monitoring/types";
import { ASSET_HEALTH_TO_STATUS } from "@/features/monitoring/lib/status-maps";

/**
 * Health Summary (§5, Overview Level 1) — `GET /inventory/statistics`'s
 * `health_distribution`, a real backend-computed count per health
 * value, not derived by fetching and counting the full asset list
 * client-side.
 */
export function HealthSummary({ organizationId }: { organizationId: string }) {
  const query = useInventoryStatistics(organizationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.totalAssets === 0 ? (
          <EmptyState
            title="No assets yet"
            description="Nothing has been discovered or registered for this organization yet."
          />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Card>
              <CardContent className="flex flex-col items-start gap-2 p-4">
                <p className="text-muted-foreground text-xs">Total</p>
                <p className="text-2xl font-semibold tabular-nums">{query.data.totalAssets}</p>
              </CardContent>
            </Card>
            {ASSET_HEALTH_STATUSES.filter((state) => (query.data.healthDistribution[state] ?? 0) > 0).map((state) => (
              <Card key={state}>
                <CardContent className="flex flex-col items-start gap-2 p-4">
                  <StatusIndicator state={ASSET_HEALTH_TO_STATUS[state as AssetHealthValue]} />
                  <p className="text-2xl font-semibold tabular-nums">{query.data.healthDistribution[state]}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        ))}
    </SectionState>
  );
}
