/**
 * `services/api-gateway-service/app/api/health.py` — `GET /health`, the
 * gateway's own unauthenticated liveness check. Migrated verbatim from
 * the original `modules/dashboard/services/health-service.ts`.
 */

import { apiClient } from "@/api/client";

export interface GatewayLiveness {
  status: "healthy";
  service: string;
  version: string;
  environment: string;
}

export const gatewayLivenessApi = {
  fetchLiveness: () => apiClient.get<GatewayLiveness>("/health"),
};
