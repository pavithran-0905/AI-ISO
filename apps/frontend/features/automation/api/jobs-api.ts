/**
 * `services/automation-service/app/api/jobs.py` — confirmed by source
 * inspection. `GET /automation/jobs` supports only `organization_id`
 * (required) — no pagination, filtering, search, or sort exist on this
 * endpoint, so every list-shaping operation happens client-side over
 * its complete result.
 *
 * `cancel`/`pause`/`resume` deliberately take a **job** id, not an
 * execution id: the backend resolves "the job's currently-active run"
 * itself. See `docs/frontend/developer-guide/automation.md`.
 */

import { apiClient } from "@/api/client";
import type {
  AutomationExecution,
  AutomationJob,
  AutomationJobCreateInput,
  AutomationJobUpdateInput,
  AutomationTypeValue,
  ExecutionModeValue,
  JobStatusValue,
  PlaybookTypeValue,
  RunAutomationInput,
} from "@/features/automation/types";
import { toAutomationExecution, type AutomationExecutionResponseBody } from "@/features/automation/api/execution-mapper";

interface AutomationJobResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  description: string | null;
  automation_type: AutomationTypeValue;
  playbook_type: PlaybookTypeValue;
  status: JobStatusValue;
  execution_mode: ExecutionModeValue;
  content: string;
  target_selector: Record<string, unknown>;
  variables: Record<string, unknown>;
  tags: string[];
  timeout_seconds: number | null;
  owner_id: string | null;
}

function toAutomationJob(body: AutomationJobResponseBody): AutomationJob {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    name: body.name,
    description: body.description,
    automationType: body.automation_type,
    playbookType: body.playbook_type,
    status: body.status,
    executionMode: body.execution_mode,
    content: body.content,
    targetSelector: body.target_selector,
    variables: body.variables,
    tags: body.tags,
    timeoutSeconds: body.timeout_seconds,
    ownerId: body.owner_id,
  };
}

export const jobsApi = {
  async list(organizationId: string): Promise<AutomationJob[]> {
    const body = await apiClient.get<AutomationJobResponseBody[]>(
      `/automation/jobs?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toAutomationJob);
  },

  async getById(jobId: string): Promise<AutomationJob> {
    const body = await apiClient.get<AutomationJobResponseBody>(`/automation/jobs/${encodeURIComponent(jobId)}`);
    return toAutomationJob(body);
  },

  /** The backend hard-codes the new job's status to `active` and
   * ignores any client-supplied value — there is no `status` field on
   * the create request at all. */
  async create(input: AutomationJobCreateInput): Promise<AutomationJob> {
    const body = await apiClient.post<AutomationJobResponseBody>("/automation/jobs", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      name: input.name,
      description: input.description,
      automation_type: input.automationType,
      playbook_type: input.playbookType,
      execution_mode: input.executionMode,
      content: input.content,
      target_selector: input.targetSelector,
      variables: input.variables,
      tags: input.tags,
      timeout_seconds: input.timeoutSeconds,
      owner_id: input.ownerId,
    });
    return toAutomationJob(body);
  },

  /** A **full replace**. `status` in particular must always be sent:
   * the backend's own schema defaults it to `draft`, so omitting it
   * silently demotes an active job. `AutomationJobUpdateInput` makes
   * every field required for exactly that reason. */
  async update(jobId: string, input: AutomationJobUpdateInput): Promise<AutomationJob> {
    const body = await apiClient.put<AutomationJobResponseBody>(`/automation/jobs/${encodeURIComponent(jobId)}`, {
      name: input.name,
      description: input.description,
      status: input.status,
      automation_type: input.automationType,
      playbook_type: input.playbookType,
      execution_mode: input.executionMode,
      content: input.content,
      target_selector: input.targetSelector,
      variables: input.variables,
      tags: input.tags,
      timeout_seconds: input.timeoutSeconds,
      owner_id: input.ownerId,
    });
    return toAutomationJob(body);
  },

  async remove(jobId: string): Promise<void> {
    await apiClient.delete<{ success: boolean }>(`/automation/jobs/${encodeURIComponent(jobId)}`);
  },

  /** Asynchronous: returns a `pending` execution immediately and the
   * real run happens on a queue worker. Callers poll the execution. */
  async run(jobId: string, input: RunAutomationInput): Promise<AutomationExecution> {
    const body = await apiClient.post<AutomationExecutionResponseBody>(
      `/automation/jobs/${encodeURIComponent(jobId)}/execute`,
      {
        target_ids: input.targetIds,
        variables: input.variables,
        execution_mode: input.executionMode,
        timeout_seconds: input.timeoutSeconds,
      },
    );
    return toAutomationExecution(body);
  },

  /** Acts on the job's currently-active execution. Cooperative, not
   * preemptive — in-flight work finishes even after the status flips. */
  async cancel(jobId: string): Promise<AutomationExecution> {
    const body = await apiClient.post<AutomationExecutionResponseBody>(`/automation/jobs/${encodeURIComponent(jobId)}/cancel`);
    return toAutomationExecution(body);
  },

  async pause(jobId: string): Promise<AutomationExecution> {
    const body = await apiClient.post<AutomationExecutionResponseBody>(`/automation/jobs/${encodeURIComponent(jobId)}/pause`);
    return toAutomationExecution(body);
  },

  /** The response still reports `paused` — the backend re-enqueues the
   * run and only the worker flips it to `running`. Callers must not
   * treat the returned status as the post-action state. */
  async resume(jobId: string): Promise<AutomationExecution> {
    const body = await apiClient.post<AutomationExecutionResponseBody>(`/automation/jobs/${encodeURIComponent(jobId)}/resume`);
    return toAutomationExecution(body);
  },
};
