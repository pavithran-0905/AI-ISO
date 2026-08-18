import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

export function useAlertHistory(alertId: string | null) {
  return useQuery({
    queryKey: ["alerts", alertId, "history"],
    queryFn: () => alertsApi.listHistory(alertId as string),
    enabled: alertId !== null,
    staleTime: 15_000,
  });
}
