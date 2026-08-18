import { useMutation, useQueryClient } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

/** See `use-acknowledge-alert.ts`'s docstring — same confirmed-response,
 * broad-invalidation pattern. */
export function useEscalateAlert(alertId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (options?: { policyId?: string; reason?: string }) => alertsApi.escalate(alertId, options),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
