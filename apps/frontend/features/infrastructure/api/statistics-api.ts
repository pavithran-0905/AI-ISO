/**
 * `services/inventory-service/app/api/statistics.py` + `analytics.py`
 * — confirmed by source inspection.
 */

import { apiClient } from "@/api/client";
import type { InventoryAnalytics, InventoryStatistics } from "@/features/infrastructure/types";

interface InventoryStatisticsResponseBody {
  total_assets: number;
  total_relationships: number;
  type_distribution: Record<string, number>;
  health_distribution: Record<string, number>;
  lifecycle_distribution: Record<string, number>;
  os_distribution: Record<string, number>;
  vendor_distribution: Record<string, number>;
  location_distribution: Record<string, number>;
  computed_at: string;
}

interface InventoryAnalyticsResponseBody extends InventoryStatisticsResponseBody {
  discovery_source_distribution: Record<string, number>;
  assets_added_last_30_days: number;
}

function toStatistics(body: InventoryStatisticsResponseBody): InventoryStatistics {
  return {
    totalAssets: body.total_assets,
    totalRelationships: body.total_relationships,
    typeDistribution: body.type_distribution,
    healthDistribution: body.health_distribution,
    lifecycleDistribution: body.lifecycle_distribution,
    osDistribution: body.os_distribution,
    vendorDistribution: body.vendor_distribution,
    locationDistribution: body.location_distribution,
    computedAt: body.computed_at,
  };
}

export const statisticsApi = {
  async fetch(organizationId: string): Promise<InventoryStatistics> {
    const body = await apiClient.get<InventoryStatisticsResponseBody>(
      `/inventory/statistics?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return toStatistics(body);
  },

  async fetchAnalytics(organizationId: string): Promise<InventoryAnalytics> {
    const body = await apiClient.get<InventoryAnalyticsResponseBody>(
      `/inventory/analytics?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return {
      ...toStatistics(body),
      discoverySourceDistribution: body.discovery_source_distribution,
      assetsAddedLast30Days: body.assets_added_last_30_days,
    };
  },
};
