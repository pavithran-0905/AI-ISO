import { useQuery } from "@tanstack/react-query";

import { alertStatisticsApi } from "@/features/alerting/api/alert-statistics-api";

export function useAlertStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["alert-statistics", organizationId],
    queryFn: () => alertStatisticsApi.fetch(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}
