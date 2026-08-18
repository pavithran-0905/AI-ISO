/**
 * `services/ai-assistant-service/app/api/agents.py` — confirmed by
 * source inspection. Read-only here: no agent/tool creation UI exists
 * in this feature (see the developer guide for why — briefly, agent
 * and tool registration is an operator/config-time activity with no
 * V1 CRUD affordance elsewhere in the app either, and building one
 * bespoke create form for a single, rarely-touched resource wasn't
 * judged worth the surface area). Listed here purely to label
 * `ToolCall.toolId` and `AiStatistics.toolUsage` keys with real names,
 * and to populate the model-provider picker on the Prompts render form.
 */

import { apiClient } from "@/api/client";
import type { Agent, AgentTypeValue, ModelProviderValue, Tool } from "@/features/ai-assistant/types";

interface AgentResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  agent_type: AgentTypeValue;
  description: string | null;
  provider: ModelProviderValue;
  model: string;
  tool_keys: string[];
  temperature: number;
  max_tokens: number;
  enabled: boolean;
}

interface ToolResponseBody {
  id: string;
  organization_id: string;
  tool_key: string;
  name: string;
  description: string;
  tool_kind: string;
  required_permission: string | null;
  is_mutating: boolean;
  enabled: boolean;
}

interface ModelProviderResponseBody {
  provider: ModelProviderValue;
  is_default: boolean;
}

function toAgent(body: AgentResponseBody): Agent {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    name: body.name,
    agentType: body.agent_type,
    description: body.description,
    provider: body.provider,
    model: body.model,
    toolKeys: body.tool_keys,
    temperature: body.temperature,
    maxTokens: body.max_tokens,
    enabled: body.enabled,
  };
}

function toTool(body: ToolResponseBody): Tool {
  return {
    id: body.id,
    organizationId: body.organization_id,
    toolKey: body.tool_key,
    name: body.name,
    description: body.description,
    toolKind: body.tool_kind,
    requiredPermission: body.required_permission,
    isMutating: body.is_mutating,
    enabled: body.enabled,
  };
}

export const catalogApi = {
  async listAgents(organizationId: string): Promise<Agent[]> {
    const body = await apiClient.get<AgentResponseBody[]>(
      `/ai/agents?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toAgent);
  },

  async listTools(organizationId: string): Promise<Tool[]> {
    const body = await apiClient.get<ToolResponseBody[]>(
      `/ai/tools?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toTool);
  },

  /** `is_default` is computed server-side as "alphabetically first
   * configured provider" — not a real configured default. Never
   * rendered as a "default" badge in this feature's UI for that
   * reason; kept on the type only for completeness. */
  async listModels(): Promise<{ provider: ModelProviderValue; isDefault: boolean }[]> {
    const body = await apiClient.get<ModelProviderResponseBody[]>("/ai/models");
    return body.map((entry) => ({ provider: entry.provider, isDefault: entry.is_default }));
  },
};
