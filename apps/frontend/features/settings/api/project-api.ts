/**
 * `services/project-service` — `/projects` (list, org-scoped,
 * unbounded — picker use only), `/projects/{id}` (`PATCH`, real
 * partial update), `/projects/{id}/settings` (`PUT` only, no `PATCH`
 * counterpart on this sub-resource).
 */

import { apiClient } from "@/api/client";
import type {
  PatchProjectInput,
  ProjectSettings,
  ProjectSummary,
  UpdateProjectSettingsInput,
} from "@/features/settings/types";

interface ProjectResponseBody {
  id: string;
  organization_id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  code: string | null;
  status: string;
  owner_id: string;
  visibility: string;
  default_language: string;
  timezone: string;
  category: string | null;
  priority: string;
  archived_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function toProjectSummary(body: ProjectResponseBody): ProjectSummary {
  return {
    id: body.id,
    organizationId: body.organization_id,
    name: body.name,
    displayName: body.display_name,
    description: body.description,
    code: body.code,
    status: body.status,
    ownerId: body.owner_id,
    visibility: body.visibility,
    defaultLanguage: body.default_language,
    timezone: body.timezone,
    category: body.category,
    priority: body.priority,
    archivedAt: body.archived_at,
    metadata: body.metadata,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

interface ProjectSettingsBody {
  default_environment: string | null;
  default_connector_id: string | null;
  default_workflow_runtime: string | null;
  notification_settings: Record<string, unknown>;
  retention_policies: Record<string, unknown>;
  execution_policies: Record<string, unknown>;
  automation_policies: Record<string, unknown>;
  validation_policies: Record<string, unknown>;
  monitoring_policies: Record<string, unknown>;
  ai_settings: Record<string, unknown>;
  storage_policies: Record<string, unknown>;
  security_policies: Record<string, unknown>;
}

function toProjectSettings(body: ProjectSettingsBody): ProjectSettings {
  return {
    defaultEnvironment: body.default_environment,
    defaultConnectorId: body.default_connector_id,
    defaultWorkflowRuntime: body.default_workflow_runtime,
    notificationSettings: body.notification_settings,
    retentionPolicies: body.retention_policies,
    executionPolicies: body.execution_policies,
    automationPolicies: body.automation_policies,
    validationPolicies: body.validation_policies,
    monitoringPolicies: body.monitoring_policies,
    aiSettings: body.ai_settings,
    storagePolicies: body.storage_policies,
    securityPolicies: body.security_policies,
  };
}

export const projectApi = {
  /** Unbounded, org-scoped, server-side visibility-filtered — only
   * ever used for this feature's project picker, matching the same
   * precedent as `assetsApi.listAll` (Prompt 011). */
  async listForOrganization(organizationId: string): Promise<ProjectSummary[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<ProjectResponseBody[]>(`/projects?${query.toString()}`);
    return body.map(toProjectSummary);
  },

  /** `PATCH` — genuinely partial (`exclude_unset`), used instead of
   * this service's own `PUT` for the same "PATCH, never PUT" reason
   * established in Prompt 011. */
  async patch(projectId: string, input: PatchProjectInput): Promise<ProjectSummary> {
    const body = await apiClient.patch<ProjectResponseBody>(`/projects/${projectId}`, {
      name: input.name,
      display_name: input.displayName,
      description: input.description,
      status: input.status,
      visibility: input.visibility,
      default_language: input.defaultLanguage,
      timezone: input.timezone,
      category: input.category,
      priority: input.priority,
      metadata: input.metadata,
    });
    return toProjectSummary(body);
  },

  async getSettings(projectId: string): Promise<ProjectSettings> {
    const body = await apiClient.get<ProjectSettingsBody>(`/projects/${projectId}/settings`);
    return toProjectSettings(body);
  },

  /** Full-replace `PUT` (confirmed: no `PATCH` exists for this
   * sub-resource) — always resend the complete object. */
  async updateSettings(projectId: string, input: UpdateProjectSettingsInput): Promise<ProjectSettings> {
    const body = await apiClient.put<ProjectSettingsBody>(`/projects/${projectId}/settings`, {
      default_environment: input.defaultEnvironment,
      default_connector_id: input.defaultConnectorId,
      default_workflow_runtime: input.defaultWorkflowRuntime,
      notification_settings: input.notificationSettings,
      retention_policies: input.retentionPolicies,
      execution_policies: input.executionPolicies,
      automation_policies: input.automationPolicies,
      validation_policies: input.validationPolicies,
      monitoring_policies: input.monitoringPolicies,
      ai_settings: input.aiSettings,
      storage_policies: input.storagePolicies,
      security_policies: input.securityPolicies,
    });
    return toProjectSettings(body);
  },
};
