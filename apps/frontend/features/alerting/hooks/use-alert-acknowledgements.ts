import { useQuery } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

export function useAlertAcknowledgements(alertId: string | null) {
  return useQuery({
    queryKey: ["alerts", alertId, "acknowledgements"],
    queryFn: () => alertsApi.listAcknowledgements(alertId as string),
    enabled: alertId !== null,
    staleTime: 15_000,
  });
}
