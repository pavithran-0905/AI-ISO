import { apiClient } from "@/api/client";

import type { GatewayHealth } from "../types/health";

export const healthService = {
  getGatewayHealth: () => apiClient.get<GatewayHealth>("/health"),
};
