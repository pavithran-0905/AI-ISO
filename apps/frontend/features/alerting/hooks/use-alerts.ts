import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";
import type { AlertListParams } from "@/features/alerting/types";

export function useAlerts(params: AlertListParams | null) {
  return useQuery({
    queryKey: ["alerts", params],
    queryFn: () => alertsApi.list(params as AlertListParams),
    enabled: params !== null,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}
