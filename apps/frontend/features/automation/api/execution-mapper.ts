/**
 * The `AutomationExecutionResponse` adapter, shared by `jobs-api.ts`
 * (which returns an execution from run/cancel/pause/resume) and
 * `executions-api.ts` — kept in its own module so neither imports the
 * other.
 */

import type { AutomationExecution, ExecutionModeValue, ExecutionStatusValue } from "@/features/automation/types";

export interface AutomationExecutionResponseBody {
  id: string;
  organization_id: string;
  job_id: string;
  execution_plan_id: string | null;
  status: ExecutionStatusValue;
  execution_mode: ExecutionModeValue;
  triggered_by: string | null;
  variables: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  timeout_seconds: number | null;
  error_message: string | null;
  created_at: string;
}

export function toAutomationExecution(body: AutomationExecutionResponseBody): AutomationExecution {
  return {
    id: body.id,
    organizationId: body.organization_id,
    jobId: body.job_id,
    executionPlanId: body.execution_plan_id,
    status: body.status,
    executionMode: body.execution_mode,
    triggeredBy: body.triggered_by,
    variables: body.variables,
    startedAt: body.started_at,
    completedAt: body.completed_at,
    timeoutSeconds: body.timeout_seconds,
    errorMessage: body.error_message,
    createdAt: body.created_at,
  };
}
