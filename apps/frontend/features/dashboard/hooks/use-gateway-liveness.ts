import { useQuery } from "@tanstack/react-query";

import { gatewayLivenessApi } from "@/features/dashboard/api/gateway-liveness-api";

/** Migrated from the original `modules/dashboard` placeholder (Prompt
 * 001) — the one card on this dashboard that needs no organization
 * context: gateway liveness, not per-service health (see
 * `use-gateway-health.ts` for that). */
export function useGatewayLiveness() {
  return useQuery({
    queryKey: ["gateway", "liveness"],
    queryFn: gatewayLivenessApi.fetchLiveness,
    refetchInterval: 15_000,
  });
}
