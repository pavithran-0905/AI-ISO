import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

export function useAlertCorrelations(alertId: string | null) {
  return useQuery({
    queryKey: ["alerts", alertId, "correlations"],
    queryFn: () => alertsApi.listCorrelations(alertId as string),
    enabled: alertId !== null,
    staleTime: 30_000,
  });
}
