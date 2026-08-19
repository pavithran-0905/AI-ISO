import { useQuery } from "@tanstack/react-query";

import { statisticsApi } from "@/features/infrastructure/api/statistics-api";

export function useInventoryStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "statistics", organizationId],
    queryFn: () => statisticsApi.fetch(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useInventoryAnalytics(organizationId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "analytics", organizationId],
    queryFn: () => statisticsApi.fetchAnalytics(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}
