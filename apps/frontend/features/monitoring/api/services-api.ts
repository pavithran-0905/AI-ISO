/**
 * `services/observability-platform-service/app/api/observability.py` —
 * `GET /observability/topology`. Organization is resolved server-side
 * from the caller's session (`Depends(get_organization_id)`), not a
 * client-supplied query param — see the developer guide's note on why
 * this differs from every other monitoring endpoint in this feature.
 */

import { apiClient } from "@/api/client";
import type { ServiceHealthNode, ServiceNodeHealthValue } from "@/features/monitoring/types";

interface TopologyNodeResponseBody {
  service_name: string;
  health: ServiceNodeHealthValue;
  fan_in: number;
  fan_out: number;
  criticality: number;
  in_cycle: boolean;
}

interface TopologyResponseBody {
  environment: string;
  nodes: TopologyNodeResponseBody[];
}

function toServiceHealthNode(body: TopologyNodeResponseBody): ServiceHealthNode {
  return {
    serviceName: body.service_name,
    health: body.health,
    fanIn: body.fan_in,
    fanOut: body.fan_out,
    criticality: body.criticality,
    inCycle: body.in_cycle,
  };
}

export const servicesApi = {
  async fetchTopology(environment = "production"): Promise<ServiceHealthNode[]> {
    const body = await apiClient.get<TopologyResponseBody>(
      `/observability/topology?environment=${encodeURIComponent(environment)}`,
    );
    return body.nodes.map(toServiceHealthNode);
  },
};
