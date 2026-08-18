/**
 * `services/workflow-runtime-service/app/api/workflows.py` and
 * `app/api/instances.py` — confirmed by source inspection.
 *
 * Like `automation-service`, the execution-control actions
 * (`pause`/`resume`/`cancel`) take the **workflow definition** id, not
 * an instance id: the backend resolves "this workflow's currently
 * active instance" itself, and 404s when there isn't one.
 *
 * Rollback and replay routes are real but not consumed here — see
 * `docs/frontend/rfi/automation.md` for why they're deferred rather
 * than half-built.
 */

import { apiClient } from "@/api/client";
import type {
  ApprovalDecisionInput,
  ApprovalDecisionStatusValue,
  NodeExecutionStatusValue,
  Workflow,
  WorkflowApproval,
  WorkflowExecutionStep,
  WorkflowInstance,
  WorkflowInstanceStatusValue,
  WorkflowLog,
  WorkflowTriggerTypeValue,
} from "@/features/workflows/types";

interface WorkflowResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  workflow_key: string;
  name: string;
  description: string | null;
  owner: string | null;
  tags: string[];
  default_variables: Record<string, unknown>;
  current_version_number: string | null;
}

interface InstanceResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  definition_id: string;
  version_id: string;
  parent_instance_id: string | null;
  sdk_execution_id: string | null;
  status: WorkflowInstanceStatusValue;
  trigger_type: WorkflowTriggerTypeValue;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

interface StepResponseBody {
  id: string;
  instance_id: string;
  node_id: string;
  node_type: string;
  status: NodeExecutionStatusValue;
  started_at: string | null;
  finished_at: string | null;
  output: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
}

interface LogResponseBody {
  id: string;
  instance_id: string;
  node_id: string | null;
  level: string;
  message: string;
  logged_at: string;
}

interface ApprovalResponseBody {
  id: string;
  instance_id: string;
  node_id: string;
  node_type: string;
  approvers: string[];
  required_approvals: number;
  decision: ApprovalDecisionStatusValue;
  decisions_by_approver: Record<string, string>;
  comments: string | null;
  escalated_to: string | null;
  timeout_seconds: number;
  decided_at: string | null;
}

function toWorkflow(body: WorkflowResponseBody): Workflow {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    workflowKey: body.workflow_key,
    name: body.name,
    description: body.description,
    owner: body.owner,
    tags: body.tags,
    defaultVariables: body.default_variables,
    currentVersionNumber: body.current_version_number,
  };
}

function toInstance(body: InstanceResponseBody): WorkflowInstance {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    definitionId: body.definition_id,
    versionId: body.version_id,
    parentInstanceId: body.parent_instance_id,
    sdkExecutionId: body.sdk_execution_id,
    status: body.status,
    triggerType: body.trigger_type,
    triggeredBy: body.triggered_by,
    startedAt: body.started_at,
    finishedAt: body.finished_at,
    errorMessage: body.error_message,
  };
}

function toStep(body: StepResponseBody): WorkflowExecutionStep {
  return {
    id: body.id,
    instanceId: body.instance_id,
    nodeId: body.node_id,
    nodeType: body.node_type,
    status: body.status,
    startedAt: body.started_at,
    finishedAt: body.finished_at,
    output: body.output,
    error: body.error,
    attempts: body.attempts,
  };
}

function toLog(body: LogResponseBody): WorkflowLog {
  return {
    id: body.id,
    instanceId: body.instance_id,
    nodeId: body.node_id,
    level: body.level,
    message: body.message,
    loggedAt: body.logged_at,
  };
}

function toApproval(body: ApprovalResponseBody): WorkflowApproval {
  return {
    id: body.id,
    instanceId: body.instance_id,
    nodeId: body.node_id,
    nodeType: body.node_type,
    approvers: body.approvers,
    requiredApprovals: body.required_approvals,
    decision: body.decision,
    decisionsByApprover: body.decisions_by_approver,
    comments: body.comments,
    escalatedTo: body.escalated_to,
    timeoutSeconds: body.timeout_seconds,
    decidedAt: body.decided_at,
  };
}

export const workflowsApi = {
  async list(organizationId: string): Promise<Workflow[]> {
    const body = await apiClient.get<WorkflowResponseBody[]>(
      `/workflows?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toWorkflow);
  },

  async getById(workflowId: string): Promise<Workflow> {
    const body = await apiClient.get<WorkflowResponseBody>(`/workflows/${encodeURIComponent(workflowId)}`);
    return toWorkflow(body);
  },

  /** Asynchronous — returns the instance before it runs. The request
   * carries only `variables`, and those go into the queue message
   * rather than onto the instance row, so they are deliberately not
   * shown back on the instance (they aren't readable from any
   * endpoint). */
  async execute(workflowId: string, variables: Record<string, unknown>): Promise<WorkflowInstance> {
    const body = await apiClient.post<InstanceResponseBody>(`/workflows/${encodeURIComponent(workflowId)}/execute`, {
      variables,
    });
    return toInstance(body);
  },

  async pause(workflowId: string): Promise<WorkflowInstance> {
    const body = await apiClient.post<InstanceResponseBody>(`/workflows/${encodeURIComponent(workflowId)}/pause`);
    return toInstance(body);
  },

  async resume(workflowId: string): Promise<WorkflowInstance> {
    const body = await apiClient.post<InstanceResponseBody>(`/workflows/${encodeURIComponent(workflowId)}/resume`);
    return toInstance(body);
  },

  async cancel(workflowId: string): Promise<WorkflowInstance> {
    const body = await apiClient.post<InstanceResponseBody>(`/workflows/${encodeURIComponent(workflowId)}/cancel`);
    return toInstance(body);
  },

  async listInstances(organizationId: string, status?: WorkflowInstanceStatusValue): Promise<WorkflowInstance[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (status) query.set("status", status);
    const body = await apiClient.get<InstanceResponseBody[]>(`/workflow-instances?${query.toString()}`);
    return body.map(toInstance);
  },

  async getInstance(instanceId: string): Promise<WorkflowInstance> {
    const body = await apiClient.get<InstanceResponseBody>(`/workflow-instances/${encodeURIComponent(instanceId)}`);
    return toInstance(body);
  },

  async listInstanceSteps(instanceId: string): Promise<WorkflowExecutionStep[]> {
    const body = await apiClient.get<StepResponseBody[]>(`/workflow-instances/${encodeURIComponent(instanceId)}/steps`);
    return body.map(toStep);
  },

  async listInstanceLogs(instanceId: string): Promise<WorkflowLog[]> {
    const body = await apiClient.get<LogResponseBody[]>(`/workflow-instances/${encodeURIComponent(instanceId)}/logs`);
    return body.map(toLog);
  },

  async listInstanceApprovals(instanceId: string): Promise<WorkflowApproval[]> {
    const body = await apiClient.get<ApprovalResponseBody[]>(
      `/workflow-instances/${encodeURIComponent(instanceId)}/approvals`,
    );
    return body.map(toApproval);
  },

  async decideApproval(instanceId: string, approvalId: string, input: ApprovalDecisionInput): Promise<WorkflowApproval> {
    const body = await apiClient.post<ApprovalResponseBody>(
      `/workflow-instances/${encodeURIComponent(instanceId)}/approvals/${encodeURIComponent(approvalId)}/decide`,
      { approver: input.approver, approve: input.approve, comments: input.comments },
    );
    return toApproval(body);
  },
};
