import { useQuery } from "@tanstack/react-query";

import { automationApi } from "@/features/dashboard/api/automation-api";

export function useAutomationExecutions(organizationId: string | null) {
  return useQuery({
    queryKey: ["automation", "executions", organizationId],
    queryFn: () => automationApi.listRecentExecutions(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}
