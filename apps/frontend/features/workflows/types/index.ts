/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection of
 * `services/workflow-runtime-service` — enums from
 * `app/models/enums.py`, shapes from `app/schemas/workflow.py`,
 * `app/schemas/instance.py`, `app/schemas/approval.py`, and the
 * per-instance response models in `app/api/instances.py`.
 *
 * **This service's status vocabulary is genuinely different from
 * `automation-service`'s** — 12 values here vs 8 there, with
 * `created`/`queued`/`waiting`/`checkpointed`/`retrying`/`archived`
 * appearing only here. The two are never conflated; each is mapped
 * onto the canonical `StatusState` taxonomy independently. See
 * `docs/frontend/developer-guide/automation.md`.
 */

/** `WorkflowInstanceStatus` — `app/models/enums.py:33-50`, 12 values. */
export const WORKFLOW_INSTANCE_STATUSES = [
  "created",
  "queued",
  "waiting",
  "running",
  "paused",
  "checkpointed",
  "retrying",
  "completed",
  "cancelled",
  "failed",
  "rolled_back",
  "archived",
] as const;
export type WorkflowInstanceStatusValue = (typeof WORKFLOW_INSTANCE_STATUSES)[number];

/** The backend's own `_ACTIVE_STATUSES` (`app/services/instance.py`) —
 * drives polling and which control actions are offered. */
export const ACTIVE_INSTANCE_STATUSES: ReadonlySet<WorkflowInstanceStatusValue> = new Set([
  "created",
  "queued",
  "waiting",
  "running",
  "paused",
  "checkpointed",
  "retrying",
]);

/** `NodeExecutionStatus` — `app/models/enums.py:53-66`. */
export const NODE_EXECUTION_STATUSES = ["pending", "running", "completed", "failed", "rolled_back", "skipped"] as const;
export type NodeExecutionStatusValue = (typeof NODE_EXECUTION_STATUSES)[number];

/** `WorkflowTriggerType` — `app/models/enums.py`. */
export const WORKFLOW_TRIGGER_TYPES = ["manual", "scheduled", "event"] as const;
export type WorkflowTriggerTypeValue = (typeof WORKFLOW_TRIGGER_TYPES)[number];

/** `ApprovalDecisionStatus` — `app/models/enums.py`. */
export const APPROVAL_DECISION_STATUSES = ["pending", "approved", "rejected", "escalated", "expired"] as const;
export type ApprovalDecisionStatusValue = (typeof APPROVAL_DECISION_STATUSES)[number];

/** `WorkflowResponse` — `app/schemas/workflow.py:72-84`. `owner` is a
 * free-text string here, not a UUID (unlike automation's `owner_id`).
 * No timestamps are exposed. */
export interface Workflow {
  id: string;
  organizationId: string;
  projectId: string | null;
  workflowKey: string;
  name: string;
  description: string | null;
  owner: string | null;
  tags: string[];
  defaultVariables: Record<string, unknown>;
  currentVersionNumber: string | null;
}

/**
 * `WorkflowInstanceResponse` — `app/schemas/instance.py:15-30`. Note
 * `finishedAt`, not `completedAt` (automation-service uses the other
 * name), and there is no `createdAt` and no duration field.
 */
export interface WorkflowInstance {
  id: string;
  organizationId: string;
  projectId: string | null;
  definitionId: string;
  versionId: string;
  parentInstanceId: string | null;
  sdkExecutionId: string | null;
  status: WorkflowInstanceStatusValue;
  triggerType: WorkflowTriggerTypeValue;
  triggeredBy: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  errorMessage: string | null;
}

/** `WorkflowExecutionStepResponse` — one DAG node's own run. This
 * per-node breakdown has no equivalent in `automation-service`, whose
 * step rows exist but have no route. */
export interface WorkflowExecutionStep {
  id: string;
  instanceId: string;
  nodeId: string;
  nodeType: string;
  status: NodeExecutionStatusValue;
  startedAt: string | null;
  finishedAt: string | null;
  output: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
}

/** `WorkflowLogResponse` — note it carries no `metadata` field, unlike
 * `automation-service`'s own execution log. */
export interface WorkflowLog {
  id: string;
  instanceId: string;
  nodeId: string | null;
  level: string;
  message: string;
  loggedAt: string;
}

/** `WorkflowApprovalResponse` — `app/schemas/approval.py:33-47`. */
export interface WorkflowApproval {
  id: string;
  instanceId: string;
  nodeId: string;
  nodeType: string;
  approvers: string[];
  requiredApprovals: number;
  decision: ApprovalDecisionStatusValue;
  decisionsByApprover: Record<string, string>;
  comments: string | null;
  escalatedTo: string | null;
  timeoutSeconds: number;
  decidedAt: string | null;
}

export interface ApprovalDecisionInput {
  approver: string;
  approve: boolean;
  comments?: string;
}
