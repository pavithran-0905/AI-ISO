import { useMutation, useQueryClient } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

/**
 * §12/§29: waits for the backend's confirmed response before the UI
 * shows the alert as acknowledged — no optimistic update, since a
 * failed mutation must never make an alert appear acknowledged when it
 * isn't. On success, invalidates every query keyed under `"alerts"`
 * (the list, this alert's detail, and its history/acknowledgements
 * sub-resources all share that prefix) so nothing shows stale state.
 */
export function useAcknowledgeAlert(alertId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (comment?: string) => alertsApi.acknowledge(alertId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
