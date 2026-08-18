/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection of `services/automation-service`
 * — enums from `app/models/enums.py`, request/response shapes from
 * `app/schemas/job.py` and `app/schemas/execution.py`. See
 * `docs/frontend/developer-guide/automation.md` for the endpoint each
 * one comes from.
 *
 * This is the canonical home for automation data — `features/dashboard`
 * (Prompt 005) originally had its own copy of `AutomationExecution`/
 * `ExecutionStatusValue`, consolidated in here (Prompt 009) so the
 * Dashboard's "Recent activity" section and this feature share one
 * fetch path (§28: "do not duplicate automation API logic in
 * Dashboard").
 */

/** `ExecutionStatus` — `app/models/enums.py:110-127`. Deliberately NOT
 * the `queued`/`succeeded` vocabulary §8 speculates about: the real
 * values are `pending` and `completed`. `rolled_back` is declared but
 * never assigned by any reachable code path — kept in the union
 * because the API could still return it, never produced by the UI. */
export const EXECUTION_STATUSES = [
  "pending",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
  "timed_out",
  "rolled_back",
] as const;
export type ExecutionStatusValue = (typeof EXECUTION_STATUSES)[number];

/** Statuses the backend treats as still in-flight
 * (`app/services/execution.py`'s own `_ACTIVE_STATUSES`) — drives
 * whether the UI keeps polling and which actions it offers. */
export const ACTIVE_EXECUTION_STATUSES: ReadonlySet<ExecutionStatusValue> = new Set([
  "pending",
  "running",
  "paused",
]);

/** `JobStatus` — `app/models/enums.py:95-107`. */
export const JOB_STATUSES = ["draft", "active", "disabled", "archived"] as const;
export type JobStatusValue = (typeof JOB_STATUSES)[number];

/** `AutomationType` — `app/models/enums.py:18-40`, all 20 values. */
export const AUTOMATION_TYPES = [
  "infrastructure_automation",
  "configuration_automation",
  "provisioning",
  "decommissioning",
  "deployment",
  "patch_management",
  "software_installation",
  "firmware_upgrade",
  "os_configuration",
  "validation_execution",
  "discovery_execution",
  "monitoring_actions",
  "database_automation",
  "cloud_automation",
  "container_automation",
  "kubernetes_automation",
  "industrial_automation",
  "security_automation",
  "backup_automation",
  "custom_automation",
] as const;
export type AutomationTypeValue = (typeof AUTOMATION_TYPES)[number];

/** `PlaybookType` — `app/models/enums.py:77-92`. */
export const PLAYBOOK_TYPES = [
  "ansible_playbook",
  "python_script",
  "shell_script",
  "powershell",
  "bash",
  "tosca_service_template",
  "custom_plugin",
  "workflow_task",
  "future_dsl",
] as const;
export type PlaybookTypeValue = (typeof PLAYBOOK_TYPES)[number];

/** Playbook types the execution dispatcher can actually run today
 * (`app/dispatchers/execution_dispatcher.py`) — everything else raises
 * `DispatchError` at run time. Used to warn honestly at authoring
 * time rather than letting a job fail at 03:00. */
export const RUNNABLE_PLAYBOOK_TYPES: ReadonlySet<PlaybookTypeValue> = new Set([
  "shell_script",
  "bash",
  "python_script",
  "powershell",
  "ansible_playbook",
]);

/** `ExecutionMode` — `app/models/enums.py:63-74`. */
export const EXECUTION_MODES = [
  "immediate",
  "scheduled",
  "workflow_triggered",
  "event_triggered",
  "webhook_triggered",
  "api_triggered",
  "manual",
  "approval_required",
  "continuous",
] as const;
export type ExecutionModeValue = (typeof EXECUTION_MODES)[number];

/** `LogLevel` — `app/models/enums.py:144-154`. */
export const LOG_LEVELS = ["debug", "info", "warning", "error"] as const;
export type LogLevelValue = (typeof LOG_LEVELS)[number];

/**
 * `AutomationJobResponse` — `app/schemas/job.py:48-65`, exactly these
 * 14 fields. Note what is NOT here, all confirmed absent from the
 * response mapper (`app/api/jobs.py`'s `job_to_response`): no
 * `created_at`/`updated_at`, no `last_execution`/`next_run_at`, no
 * execution counts. See `backend-v1-integration-limitations.md`.
 */
export interface AutomationJob {
  id: string;
  organizationId: string;
  projectId: string | null;
  name: string;
  description: string | null;
  automationType: AutomationTypeValue;
  playbookType: PlaybookTypeValue;
  status: JobStatusValue;
  executionMode: ExecutionModeValue;
  /** The raw script/playbook body. */
  content: string;
  /** Free-form and, per source inspection, never read by any execution
   * code path — write-only metadata today. */
  targetSelector: Record<string, unknown>;
  /** Free-form defaults merged into an execution's own variables. NOT
   * substituted into `content` — the dispatcher never passes variables
   * to a runner. */
  variables: Record<string, unknown>;
  tags: string[];
  timeoutSeconds: number | null;
  ownerId: string | null;
}

export interface AutomationJobCreateInput {
  organizationId: string;
  projectId?: string;
  name: string;
  description?: string;
  automationType: AutomationTypeValue;
  playbookType: PlaybookTypeValue;
  executionMode: ExecutionModeValue;
  content: string;
  targetSelector?: Record<string, unknown>;
  variables?: Record<string, unknown>;
  tags?: string[];
  timeoutSeconds?: number | null;
  ownerId?: string;
}

/**
 * `AutomationJobUpdateRequest` — a **full replace**, not a partial
 * patch. Critically, `status` defaults to `draft` server-side, so
 * omitting it silently demotes an active job. Every field is therefore
 * required here, forcing callers to send the job's current values
 * explicitly. See `backend-v1-integration-limitations.md`.
 */
export interface AutomationJobUpdateInput {
  name: string;
  description: string | null;
  status: JobStatusValue;
  automationType: AutomationTypeValue;
  playbookType: PlaybookTypeValue;
  executionMode: ExecutionModeValue;
  content: string;
  targetSelector: Record<string, unknown>;
  variables: Record<string, unknown>;
  tags: string[];
  timeoutSeconds: number | null;
  ownerId: string | null;
}

/**
 * `AutomationExecutionResponse` — `app/schemas/execution.py:25-40`.
 * `createdAt` is the only timestamp always present; `startedAt`/
 * `completedAt` are null until the worker picks the run up. There is
 * no `duration` field — see `lib/duration.ts` for the client-side
 * computation, and no `result`/`output`/`exitCode` (those rows are
 * written backend-side but have no route).
 */
export interface AutomationExecution {
  id: string;
  organizationId: string;
  jobId: string;
  executionPlanId: string | null;
  status: ExecutionStatusValue;
  executionMode: ExecutionModeValue;
  triggeredBy: string | null;
  /** The merged job-defaults + per-run variables the backend stored.
   * Includes the backend's own internal `_target_ids` key when targets
   * were selected — use `splitExecutionVariables()` rather than
   * rendering this raw. */
  variables: Record<string, unknown>;
  startedAt: string | null;
  completedAt: string | null;
  timeoutSeconds: number | null;
  errorMessage: string | null;
  createdAt: string;
}

export interface RunAutomationInput {
  targetIds?: string[];
  variables?: Record<string, unknown>;
  executionMode?: ExecutionModeValue;
  timeoutSeconds?: number | null;
}

/** `AutomationExecutionLogResponse` — `app/schemas/execution_log.py:14-23`.
 * Returned oldest-first, unpaginated, one entry per execution step (a
 * truncated stdout/stderr blob), not line-by-line console output. */
export interface AutomationExecutionLog {
  id: string;
  executionId: string;
  stepId: string | null;
  level: LogLevelValue;
  message: string;
  metadata: Record<string, unknown>;
  loggedAt: string;
}

/**
 * `AutomationStatisticsResponse` — `app/schemas/statistics.py:15-28`.
 * Only the well-typed scalar fields are surfaced; `resource_usage`
 * (always `{}` server-side), `connector_usage`, `top_failed_jobs`,
 * `most_executed_jobs`, and `execution_heatmap` are `dict[str, Any]`
 * and deliberately not modelled — consistent with the discipline
 * established in Prompts 005/007/008.
 *
 * `successRate`/`failureRate` are 0–1 fractions, NOT percentages.
 * `computedAt` matters: the backend computes this snapshot once and
 * never refreshes it, so the UI must show when it was taken.
 */
export interface AutomationStatistics {
  totalJobs: number;
  totalExecutions: number;
  successRate: number;
  failureRate: number;
  averageRuntimeSeconds: number;
  computedAt: string;
}

/** `AutomationTemplateResponse` — `app/schemas/template.py`. Only list
 * and create exist; `variablesSchema` is an untyped `dict[str, Any]`
 * and is not interpreted. */
export interface AutomationTemplate {
  id: string;
  organizationId: string;
  name: string;
  description: string | null;
  automationType: AutomationTypeValue;
  playbookType: PlaybookTypeValue;
  content: string;
  variablesSchema: Record<string, unknown>;
}
