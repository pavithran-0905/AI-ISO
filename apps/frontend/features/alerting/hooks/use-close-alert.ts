import { useMutation, useQueryClient } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

/** `DELETE /alerts/{id}` — a status transition to `closed`, not a row
 * deletion. See `use-acknowledge-alert.ts`'s docstring for the shared
 * confirmed-response, broad-invalidation pattern. */
export function useCloseAlert(alertId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => alertsApi.close(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
