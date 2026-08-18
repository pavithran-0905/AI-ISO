import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

export function useAlertNotifications(alertId: string | null) {
  return useQuery({
    queryKey: ["alerts", alertId, "notifications"],
    queryFn: () => alertsApi.listNotifications(alertId as string),
    enabled: alertId !== null,
    staleTime: 30_000,
  });
}
