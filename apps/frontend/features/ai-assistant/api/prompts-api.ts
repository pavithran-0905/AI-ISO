/**
 * `services/ai-assistant-service/app/api/prompts.py` — confirmed by
 * source inspection. Nothing here is enforced server-side beyond basic
 * existence/state checks (any caller can approve or roll back any
 * prompt in the org — see `docs/frontend/backend-v1-integration-limitations.md`),
 * so this feature gates the whole page behind the coarse capability
 * model as a UX-only precaution, never a real security boundary.
 */

import { apiClient } from "@/api/client";
import type {
  AddPromptVersionInput,
  CreatePromptInput,
  Prompt,
  PromptStatusValue,
  PromptVersion,
} from "@/features/ai-assistant/types";

interface PromptResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  description: string | null;
  current_version_number: string;
  enabled: boolean;
}

interface PromptVersionResponseBody {
  id: string;
  prompt_id: string;
  version_number: string;
  template: string;
  variables: string[];
  status: PromptStatusValue;
  approved_by: string | null;
  approved_at: string | null;
}

interface PromptRenderResponseBody {
  prompt_id: string;
  version_number: string;
  rendered: string;
}

function toPrompt(body: PromptResponseBody): Prompt {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    name: body.name,
    description: body.description,
    currentVersionNumber: body.current_version_number,
    enabled: body.enabled,
  };
}

function toPromptVersion(body: PromptVersionResponseBody): PromptVersion {
  return {
    id: body.id,
    promptId: body.prompt_id,
    versionNumber: body.version_number,
    template: body.template,
    variables: body.variables,
    status: body.status,
    approvedBy: body.approved_by,
    approvedAt: body.approved_at,
  };
}

export const promptsApi = {
  async list(organizationId: string): Promise<Prompt[]> {
    const body = await apiClient.get<PromptResponseBody[]>(
      `/ai/prompts?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toPrompt);
  },

  async create(input: CreatePromptInput): Promise<Prompt> {
    const body = await apiClient.post<PromptResponseBody>("/ai/prompts", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      name: input.name,
      description: input.description,
      template: input.template,
      variables: input.variables ?? [],
    });
    return toPrompt(body);
  },

  async listVersions(promptId: string): Promise<PromptVersion[]> {
    const body = await apiClient.get<PromptVersionResponseBody[]>(
      `/ai/prompts/${encodeURIComponent(promptId)}/versions`,
    );
    return body.map(toPromptVersion);
  },

  async addVersion(promptId: string, input: AddPromptVersionInput): Promise<PromptVersion> {
    const body = await apiClient.post<PromptVersionResponseBody>(
      `/ai/prompts/${encodeURIComponent(promptId)}/versions`,
      { template: input.template, variables: input.variables ?? [] },
    );
    return toPromptVersion(body);
  },

  async approveVersion(promptId: string, versionNumber: string): Promise<PromptVersion> {
    const body = await apiClient.post<PromptVersionResponseBody>(
      `/ai/prompts/${encodeURIComponent(promptId)}/versions/${encodeURIComponent(versionNumber)}/approve`,
      {},
    );
    return toPromptVersion(body);
  },

  async rollback(promptId: string, versionNumber: string): Promise<Prompt> {
    const body = await apiClient.post<PromptResponseBody>(
      `/ai/prompts/${encodeURIComponent(promptId)}/rollback/${encodeURIComponent(versionNumber)}`,
      {},
    );
    return toPrompt(body);
  },

  async render(promptId: string, variables: Record<string, string>): Promise<string> {
    const body = await apiClient.post<PromptRenderResponseBody>(
      `/ai/prompts/${encodeURIComponent(promptId)}/render`,
      { variables },
    );
    return body.rendered;
  },
};
