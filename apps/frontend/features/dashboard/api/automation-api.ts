/**
 * `services/automation-service/app/api/executions.py` — confirmed by
 * source inspection, `GET /automation/executions` requires
 * `organization_id`, returns newest-first per the endpoint's own
 * docstring.
 */

import { apiClient } from "@/api/client";
import type { AutomationExecution, ExecutionStatusValue } from "@/features/dashboard/types";

interface AutomationExecutionResponseBody {
  id: string;
  organization_id: string;
  job_id: string;
  status: ExecutionStatusValue;
  triggered_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

function toAutomationExecution(body: AutomationExecutionResponseBody): AutomationExecution {
  return {
    id: body.id,
    organizationId: body.organization_id,
    jobId: body.job_id,
    status: body.status,
    triggeredBy: body.triggered_by,
    startedAt: body.started_at,
    completedAt: body.completed_at,
    errorMessage: body.error_message,
  };
}

export const automationApi = {
  async listRecentExecutions(organizationId: string): Promise<AutomationExecution[]> {
    const body = await apiClient.get<AutomationExecutionResponseBody[]>(
      `/automation/executions?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toAutomationExecution);
  },
};
