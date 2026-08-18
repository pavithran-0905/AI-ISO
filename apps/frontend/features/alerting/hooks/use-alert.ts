import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

export function useAlert(alertId: string | null) {
  return useQuery({
    queryKey: ["alerts", alertId],
    queryFn: () => alertsApi.getById(alertId as string),
    enabled: alertId !== null,
    staleTime: 15_000,
  });
}
