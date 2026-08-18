import { useQuery } from "@tanstack/react-query";

import { catalogApi } from "@/features/ai-assistant/api/catalog-api";

/** Read-only catalog data — used to label `ToolCall.toolId` and
 * `AiStatistics.toolUsage` keys with real names, and to populate the
 * provider picker on the Prompts render form. See `catalog-api.ts` for
 * why there is no create/update/delete here. */
export function useAgents(organizationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "agents", organizationId],
    queryFn: () => catalogApi.listAgents(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useTools(organizationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "tools", organizationId],
    queryFn: () => catalogApi.listTools(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useModelProviders() {
  return useQuery({
    queryKey: ["ai-assistant", "models"],
    queryFn: () => catalogApi.listModels(),
    staleTime: 300_000,
  });
}
