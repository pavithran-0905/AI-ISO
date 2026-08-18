/**
 * `services/automation-service/app/api/executions.py` — confirmed by
 * source inspection. `GET /automation/executions` accepts exactly two
 * params, `organization_id` (required) and `status`, and returns every
 * matching execution newest-first with no limit. Everything else the
 * Executions page offers (job filter, search, date range, paging) is
 * therefore applied client-side over that complete result.
 *
 * The artifacts endpoint is real but no backend writer ever produces
 * an artifact row, so it is not consumed here — see
 * `docs/frontend/backend-v1-integration-limitations.md`.
 */

import { apiClient } from "@/api/client";
import { toAutomationExecution, type AutomationExecutionResponseBody } from "@/features/automation/api/execution-mapper";
import type {
  AutomationExecution,
  AutomationExecutionLog,
  ExecutionStatusValue,
  LogLevelValue,
} from "@/features/automation/types";

interface ExecutionLogResponseBody {
  id: string;
  execution_id: string;
  step_id: string | null;
  level: LogLevelValue;
  message: string;
  metadata: Record<string, unknown>;
  logged_at: string;
}

function toExecutionLog(body: ExecutionLogResponseBody): AutomationExecutionLog {
  return {
    id: body.id,
    executionId: body.execution_id,
    stepId: body.step_id,
    level: body.level,
    message: body.message,
    metadata: body.metadata,
    loggedAt: body.logged_at,
  };
}

export interface ExecutionListParams {
  organizationId: string;
  status?: ExecutionStatusValue;
}

export const executionsApi = {
  async list(params: ExecutionListParams): Promise<AutomationExecution[]> {
    const query = new URLSearchParams({ organization_id: params.organizationId });
    if (params.status) query.set("status", params.status);
    const body = await apiClient.get<AutomationExecutionResponseBody[]>(`/automation/executions?${query.toString()}`);
    return body.map(toAutomationExecution);
  },

  async getById(executionId: string): Promise<AutomationExecution> {
    const body = await apiClient.get<AutomationExecutionResponseBody>(
      `/automation/executions/${encodeURIComponent(executionId)}`,
    );
    return toAutomationExecution(body);
  },

  /** Oldest-first, unpaginated. One entry per execution step — a
   * truncated stdout/stderr blob — not line-by-line console output. */
  async listLogs(executionId: string): Promise<AutomationExecutionLog[]> {
    const body = await apiClient.get<ExecutionLogResponseBody[]>(
      `/automation/executions/${encodeURIComponent(executionId)}/logs`,
    );
    return body.map(toExecutionLog);
  },
};
