/**
 * `services/ai-assistant-service/app/api/chat.py` — confirmed by
 * source inspection. `POST /ai/chat` is fully synchronous: the entire
 * guardrail/RAG/tool/model pipeline runs inside the request, and a
 * message doesn't exist until this response arrives complete — there
 * is no "generating" placeholder to poll.
 *
 * `POST /ai/chat/stream` exists but is not used here: it awaits the
 * exact same complete pipeline first, then chops the already-finished
 * answer into fixed 256-character chunks and drips them out over SSE.
 * It gives zero time-to-first-token improvement over the endpoint
 * below — the user waits the identical total latency either way — so
 * consuming it would only add a cosmetic typewriter effect while
 * implying real incremental generation, which §10 explicitly forbids
 * faking. See `docs/frontend/backend-v1-integration-limitations.md`.
 */

import { apiClient } from "@/api/client";
import type {
  ChatResult,
  Citation,
  Conversation,
  ConversationStatusValue,
  Message,
  MessageRoleValue,
  SendMessageInput,
  ToolCall,
  ToolCallStatusValue,
} from "@/features/ai-assistant/types";

interface CitationBody {
  chunk_id: string;
  document_id: string;
  title: string;
  uri: string | null;
  score: number;
}

interface ChatResponseBody {
  conversation_id: string;
  message_id: string;
  content: string;
  citations: CitationBody[];
  tool_calls_made: number;
  guardrail_findings: string[];
  provider: string | null;
  model: string | null;
}

interface ConversationResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  session_id: string | null;
  user_id: string;
  title: string;
  status: ConversationStatusValue;
  started_at: string;
  completed_at: string | null;
}

interface MessageResponseBody {
  id: string;
  conversation_id: string;
  sequence: number;
  role: MessageRoleValue;
  content: string;
  model: string | null;
  provider: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number | null;
  citations: CitationBody[];
}

interface ToolCallResponseBody {
  id: string;
  conversation_id: string | null;
  tool_id: string;
  arguments: Record<string, unknown>;
  status: ToolCallStatusValue;
  denial_reason: string | null;
  requested_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  succeeded: boolean | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  duration_ms: number | null;
}

function toCitation(body: CitationBody): Citation {
  return { chunkId: body.chunk_id, documentId: body.document_id, title: body.title, uri: body.uri, score: body.score };
}

function toConversation(body: ConversationResponseBody): Conversation {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    sessionId: body.session_id,
    userId: body.user_id,
    title: body.title,
    status: body.status,
    startedAt: body.started_at,
    completedAt: body.completed_at,
  };
}

function toMessage(body: MessageResponseBody): Message {
  return {
    id: body.id,
    conversationId: body.conversation_id,
    sequence: body.sequence,
    role: body.role,
    content: body.content,
    model: body.model,
    provider: body.provider,
    promptTokens: body.prompt_tokens,
    completionTokens: body.completion_tokens,
    latencyMs: body.latency_ms,
    citations: body.citations.map(toCitation),
  };
}

function toToolCall(body: ToolCallResponseBody): ToolCall {
  return {
    id: body.id,
    conversationId: body.conversation_id,
    toolId: body.tool_id,
    arguments: body.arguments,
    status: body.status,
    denialReason: body.denial_reason,
    requestedBy: body.requested_by,
    startedAt: body.started_at,
    finishedAt: body.finished_at,
    succeeded: body.succeeded,
    result: body.result,
    errorMessage: body.error_message,
    durationMs: body.duration_ms,
  };
}

export const chatApi = {
  async send(input: SendMessageInput): Promise<ChatResult> {
    const body = await apiClient.post<ChatResponseBody>("/ai/chat", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      conversation_id: input.conversationId,
      message: input.message,
      agent_type: input.agentType,
      allow_mutating_tools: input.allowMutatingTools ?? false,
      caller_permissions: input.callerPermissions ?? [],
    });
    return {
      conversationId: body.conversation_id,
      messageId: body.message_id,
      content: body.content,
      citations: body.citations.map(toCitation),
      toolCallsMade: body.tool_calls_made,
      guardrailFindings: body.guardrail_findings,
      provider: body.provider,
      model: body.model,
    };
  },

  async listConversations(organizationId: string, mineOnly: boolean): Promise<Conversation[]> {
    const query = new URLSearchParams({ organization_id: organizationId, mine_only: String(mineOnly) });
    const body = await apiClient.get<ConversationResponseBody[]>(`/ai/conversations?${query.toString()}`);
    return body.map(toConversation);
  },

  async getConversation(conversationId: string): Promise<Conversation> {
    const body = await apiClient.get<ConversationResponseBody>(`/ai/conversations/${encodeURIComponent(conversationId)}`);
    return toConversation(body);
  },

  /** Ordered by `sequence` — the one list in this service with a real,
   * guaranteed order. */
  async listMessages(conversationId: string): Promise<Message[]> {
    const body = await apiClient.get<MessageResponseBody[]>(
      `/ai/conversations/${encodeURIComponent(conversationId)}/messages`,
    );
    return body.map(toMessage);
  },

  async listToolCalls(conversationId: string): Promise<ToolCall[]> {
    const body = await apiClient.get<ToolCallResponseBody[]>(
      `/ai/conversations/${encodeURIComponent(conversationId)}/tool-calls`,
    );
    return body.map(toToolCall);
  },
};
