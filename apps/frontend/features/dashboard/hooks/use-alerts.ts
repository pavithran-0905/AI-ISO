import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/dashboard/api/alerts-api";

export function useAlerts(organizationId: string | null) {
  return useQuery({
    queryKey: ["alerts", organizationId],
    queryFn: () => alertsApi.list(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}
