import { useQuery } from "@tanstack/react-query";

import { assetsApi } from "@/features/monitoring/api/assets-api";

export function useInventoryStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["monitoring", "inventory-statistics", organizationId],
    queryFn: () => assetsApi.fetchStatistics(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}
