/**
 * `services/automation-service/app/api/statistics.py` —
 * `GET /automation/statistics`.
 *
 * Only the well-typed scalar fields are mapped. `resource_usage`
 * (hard-coded `{}` server-side), `connector_usage`, `top_failed_jobs`,
 * `most_executed_jobs`, and `execution_heatmap` are all
 * `dict[str, Any]` with no confirmed internal shape and are
 * deliberately not surfaced.
 *
 * The backend computes this snapshot once per organization and never
 * refreshes it — `computedAt` is therefore load-bearing, not
 * decorative, and every consumer shows it.
 */

import { apiClient } from "@/api/client";
import type { AutomationStatistics } from "@/features/automation/types";

interface StatisticsResponseBody {
  total_jobs: number;
  total_executions: number;
  success_rate: number;
  failure_rate: number;
  average_runtime_seconds: number;
  computed_at: string;
}

export const statisticsApi = {
  async fetch(organizationId: string): Promise<AutomationStatistics> {
    const body = await apiClient.get<StatisticsResponseBody>(
      `/automation/statistics?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return {
      totalJobs: body.total_jobs,
      totalExecutions: body.total_executions,
      successRate: body.success_rate,
      failureRate: body.failure_rate,
      averageRuntimeSeconds: body.average_runtime_seconds,
      computedAt: body.computed_at,
    };
  },
};
