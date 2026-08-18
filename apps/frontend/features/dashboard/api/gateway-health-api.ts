/**
 * `services/api-gateway-service/app/api/gateway_health.py` —
 * `GET /gateway/health` requires `organization_id`, confirmed by
 * source inspection. Distinct from the unauthenticated `GET /health`
 * liveness check `modules/dashboard`'s original `useGatewayHealth`
 * hook used (that one is preserved as-is — see
 * `@/features/dashboard/hooks/use-gateway-liveness`) — this is the
 * real per-service aggregated health, `overall_status` = worst of
 * every registered instance.
 */

import { apiClient } from "@/api/client";
import type { AggregatedGatewayHealth, HealthStateValue, ServiceHealthInstance } from "@/features/dashboard/types";

interface ServiceHealthResponseBody {
  service_id: string;
  instance_url: string;
  status: HealthStateValue;
  latency_ms: number | null;
  error: string | null;
  checked_at: string;
}

interface GatewayHealthResponseBody {
  overall_status: HealthStateValue;
  instances: ServiceHealthResponseBody[];
}

function toServiceHealthInstance(body: ServiceHealthResponseBody): ServiceHealthInstance {
  return {
    serviceId: body.service_id,
    instanceUrl: body.instance_url,
    status: body.status,
    latencyMs: body.latency_ms,
    error: body.error,
    checkedAt: body.checked_at,
  };
}

export const gatewayHealthApi = {
  async fetchAggregatedHealth(organizationId: string): Promise<AggregatedGatewayHealth> {
    const body = await apiClient.get<GatewayHealthResponseBody>(
      `/gateway/health?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return { overallStatus: body.overall_status, instances: body.instances.map(toServiceHealthInstance) };
  },
};
