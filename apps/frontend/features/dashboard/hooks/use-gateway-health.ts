import { useQuery } from "@tanstack/react-query";

import { gatewayHealthApi } from "@/features/dashboard/api/gateway-health-api";

export function useGatewayHealth(organizationId: string | null) {
  return useQuery({
    queryKey: ["gateway", "health", organizationId],
    queryFn: () => gatewayHealthApi.fetchAggregatedHealth(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}
