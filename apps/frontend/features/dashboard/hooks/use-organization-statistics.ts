import { useQuery } from "@tanstack/react-query";

import { organizationApi } from "@/organization/api";

export function useOrganizationStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["organizations", organizationId, "statistics"],
    queryFn: () => organizationApi.fetchStatistics(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}
