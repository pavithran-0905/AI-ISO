import { useMutation, useQueryClient } from "@tanstack/react-query";

import { alertsApi } from "@/features/alerting/api/alerts-api";

/** See `use-acknowledge-alert.ts`'s docstring — same confirmed-response,
 * broad-invalidation pattern. */
export function useResolveAlert(alertId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (resolutionNotes?: string) => alertsApi.resolve(alertId, resolutionNotes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
