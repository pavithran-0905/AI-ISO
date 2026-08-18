/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection of `services/ai-assistant-service`
 * — enums from `app/models/enums.py`, shapes from `app/schemas/chat.py`,
 * `knowledge.py`, `insight.py`, `agent.py`, `prompt.py`. See
 * `docs/frontend/developer-guide/ai-assistant.md` for the endpoint each
 * one comes from and for the security-relevant gaps this typing
 * deliberately does not paper over.
 */

/** `AgentType` — `app/models/enums.py`. A hint on `POST /ai/chat`, only
 * meaningful when starting a new conversation — the backend never
 * reports back which agent actually answered (no `agent_id` field
 * exists on any response), so this is offered as a picker at
 * conversation start and never rendered as post-hoc attribution. */
export const AGENT_TYPES = [
  "planner",
  "reasoning",
  "infrastructure",
  "automation",
  "validation",
  "monitoring",
  "configuration",
  "knowledge",
  "workflow",
  "reporting",
  "security",
  "custom",
] as const;
export type AgentTypeValue = (typeof AGENT_TYPES)[number];

export const MESSAGE_ROLES = ["system", "user", "assistant", "tool"] as const;
export type MessageRoleValue = (typeof MESSAGE_ROLES)[number];

/** A conversation's real lifecycle values. Only `active` is ever
 * actually reached through the API today — no route transitions a
 * conversation to `completed`/`failed`/`expired` (confirmed: the
 * service method that would do so is never called by any router). */
export const CONVERSATION_STATUSES = ["active", "completed", "failed", "expired"] as const;
export type ConversationStatusValue = (typeof CONVERSATION_STATUSES)[number];

export const TOOL_CALL_STATUSES = ["pending", "running", "succeeded", "failed", "denied"] as const;
export type ToolCallStatusValue = (typeof TOOL_CALL_STATUSES)[number];

export const RECOMMENDATION_TYPES = [
  "playbook",
  "workflow",
  "automation",
  "remediation",
  "root_cause",
  "capacity",
  "configuration",
  "risk",
] as const;
export type RecommendationTypeValue = (typeof RECOMMENDATION_TYPES)[number];

export const RECOMMENDATION_STATUSES = ["proposed", "accepted", "rejected", "applied"] as const;
export type RecommendationStatusValue = (typeof RECOMMENDATION_STATUSES)[number];

export const AI_REPORT_TYPES = [
  "executive",
  "operational",
  "incident_summary",
  "health_summary",
  "capacity",
  "automation",
  "validation",
  "compliance",
  "natural_language",
] as const;
export type AiReportTypeValue = (typeof AI_REPORT_TYPES)[number];

export const MEMORY_SCOPES = ["conversation", "session", "user", "organization", "project"] as const;
export type MemoryScopeValue = (typeof MEMORY_SCOPES)[number];

export const RETRIEVAL_STRATEGIES = ["vector", "keyword", "hybrid"] as const;
export type RetrievalStrategyValue = (typeof RETRIEVAL_STRATEGIES)[number];

export const DOCUMENT_SOURCE_TYPES = [
  "inventory",
  "discovery",
  "configuration_management",
  "automation",
  "workflow_runtime",
  "validation",
  "monitoring",
  "alerting",
  "reports",
  "documentation",
  "policies",
  "playbooks",
  "runbooks",
  "wiki",
  "uploaded",
] as const;
export type DocumentSourceTypeValue = (typeof DOCUMENT_SOURCE_TYPES)[number];

export const FEEDBACK_RATINGS = ["positive", "negative", "neutral"] as const;
export type FeedbackRatingValue = (typeof FEEDBACK_RATINGS)[number];

export const PROMPT_STATUSES = ["draft", "approved", "archived"] as const;
export type PromptStatusValue = (typeof PROMPT_STATUSES)[number];

export const MODEL_PROVIDERS = [
  "openai",
  "azure_openai",
  "anthropic",
  "gemini",
  "ollama",
  "vllm",
  "openrouter",
  "local",
] as const;
export type ModelProviderValue = (typeof MODEL_PROVIDERS)[number];

/**
 * A citation/source. `ChatResponse.citations`/`MessageResponse.citations`
 * are declared `list[dict[str, Any]]` at the Pydantic level (a real,
 * unused `CitationResponse` schema exists but is never the field's
 * actual type) — but the runtime shape is fully confirmed by reading
 * the one function that ever constructs one
 * (`RetrievedPassage.as_citation()`), so it's typed here rather than
 * left as `unknown`, unlike the platform's usual untyped-dict fields.
 */
export interface Citation {
  chunkId: string;
  documentId: string;
  title: string;
  uri: string | null;
  score: number;
}

/** `ConversationResponse`. */
export interface Conversation {
  id: string;
  organizationId: string;
  projectId: string | null;
  sessionId: string | null;
  userId: string;
  title: string;
  status: ConversationStatusValue;
  startedAt: string;
  completedAt: string | null;
}

/** `MessageResponse`. `content` is plain text — never structured
 * blocks/parts — so rendering only needs to sanitize and format text,
 * never interpret a content-block schema that doesn't exist. */
export interface Message {
  id: string;
  conversationId: string;
  sequence: number;
  role: MessageRoleValue;
  content: string;
  model: string | null;
  provider: string | null;
  promptTokens: number;
  completionTokens: number;
  latencyMs: number | null;
  citations: Citation[];
}

/** `ChatResponse` — the full result of one synchronous `POST /ai/chat`
 * call. There is no intermediate "generating" state to model: a
 * message doesn't exist until this response arrives complete. */
export interface ChatResult {
  conversationId: string;
  messageId: string;
  content: string;
  citations: Citation[];
  toolCallsMade: number;
  guardrailFindings: string[];
  provider: string | null;
  model: string | null;
}

export interface SendMessageInput {
  organizationId: string;
  projectId?: string;
  conversationId?: string;
  message: string;
  agentType?: AgentTypeValue;
  /** Defaults to `false` server-side. A blanket, pre-emptive opt-in
   * sent WITH the request — the real contract has no interactive
   * "the assistant wants to run X, allow?" round-trip; a mutating tool
   * is either allowed for this whole turn or denied outright within
   * it. See `MutatingToolsToggle`'s own docstring. */
  allowMutatingTools?: boolean;
  /** Trusted by the backend with NO cross-check against the caller's
   * real JWT-derived permissions — see this type's own file header and
   * `docs/frontend/backend-v1-integration-limitations.md`. Populated
   * from the existing coarse capability model as a matter of
   * consistency, never as a security boundary. */
  callerPermissions?: string[];
}

/**
 * `ToolCallResponse`. `toolId` is a bare UUID with no name on the
 * object itself — resolve it against `GET /ai/tools` to label it.
 * There is no `messageId` (the backend never populates the column that
 * would let a tool call be tied to the specific assistant message it
 * supported — only to the conversation as a whole).
 */
export interface ToolCall {
  id: string;
  conversationId: string | null;
  toolId: string;
  arguments: Record<string, unknown>;
  status: ToolCallStatusValue;
  denialReason: string | null;
  requestedBy: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  succeeded: boolean | null;
  result: Record<string, unknown> | null;
  errorMessage: string | null;
  durationMs: number | null;
}

/** `AgentResponse` — read-only in this feature; no agent/tool
 * creation UI was built (see the developer guide for why). */
export interface Agent {
  id: string;
  organizationId: string;
  projectId: string | null;
  name: string;
  agentType: AgentTypeValue;
  description: string | null;
  provider: string;
  model: string;
  toolKeys: string[];
  temperature: number;
  maxTokens: number;
  enabled: boolean;
}

/** `ToolResponse`. */
export interface Tool {
  id: string;
  organizationId: string;
  toolKey: string;
  name: string;
  description: string;
  toolKind: string;
  requiredPermission: string | null;
  isMutating: boolean;
  enabled: boolean;
}

/** `DocumentResponse`. */
export interface KnowledgeDocument {
  id: string;
  organizationId: string;
  sourceType: DocumentSourceTypeValue;
  externalId: string | null;
  title: string;
  uri: string | null;
  contentHash: string;
}

export interface IngestDocumentInput {
  organizationId: string;
  projectId?: string;
  sourceType: DocumentSourceTypeValue;
  title: string;
  text: string;
  externalId?: string;
  uri?: string;
}

export interface IngestDocumentResult {
  documentId: string;
  title: string;
  chunksCreated: number;
  skippedUnchanged: boolean;
}

/** `KnowledgeSearchHit` — the search endpoint's own real, typed
 * citation-like shape (distinct from `Citation` above — this one
 * includes the actual retrieved passage `content`, which a chat
 * citation never does). */
export interface KnowledgeSearchHit {
  chunkId: string;
  documentId: string;
  documentTitle: string;
  documentUri: string | null;
  content: string;
  score: number;
}

export interface KnowledgeSearchInput {
  organizationId: string;
  query: string;
  topK?: number;
  strategy?: RetrievalStrategyValue;
  sourceTypes?: DocumentSourceTypeValue[];
}

/** `RecommendationResponse`. No timestamp field exists on this
 * response — recommendations are shown in whatever order the backend
 * returns them (unspecified), never claimed to be "most recent
 * first". */
export interface Recommendation {
  id: string;
  organizationId: string;
  conversationId: string | null;
  recommendationType: RecommendationTypeValue;
  title: string;
  body: string;
  rationale: string | null;
  citations: Citation[];
  confidence: number | null;
  status: RecommendationStatusValue;
  decidedBy: string | null;
}

export interface GenerateRecommendationInput {
  organizationId: string;
  projectId?: string;
  conversationId?: string;
  recommendationType: RecommendationTypeValue;
  subject: string;
}

/** `AiReportResponse` — a genuinely distinct resource from
 * `reporting-service`'s own `Report`/`Template`/`Execution` model
 * (Prompt 008); the two share no id space. `reporting-service` can
 * optionally embed a narrative generated by calling this same backend
 * internally (its `AI_SUMMARY` section kind) — that is a separate,
 * server-to-server integration this frontend doesn't orchestrate. */
export interface AiReport {
  id: string;
  organizationId: string;
  conversationId: string | null;
  reportType: AiReportTypeValue;
  title: string;
  body: string;
  parameters: Record<string, unknown>;
  citations: Citation[];
  generatedBy: string | null;
  generatedAt: string;
}

export interface GenerateAiReportInput {
  organizationId: string;
  projectId?: string;
  conversationId?: string;
  reportType: AiReportTypeValue;
  subject: string;
  parameters?: Record<string, unknown>;
}

/** `MemoryResponse` — read-only in this feature. No delete/clear
 * endpoint exists despite the prompt's own request for one (§24); see
 * the limitations doc. */
export interface MemoryEntry {
  id: string;
  scope: MemoryScopeValue;
  scopeReference: string;
  key: string;
  value: string;
  importance: number;
  expiresAt: string | null;
}

/**
 * `AiStatisticsResponse`. `toolUsage`/`agentUsage`/`modelUsage` are
 * `dict[str, Any]` at the schema level; their real, confirmed runtime
 * shapes are `Record<string, number>` (all three are `Counter(...)`
 * results server-side) — typed here because the shape is confirmed,
 * unlike the platform's usual "leave it untyped" untyped-dict
 * discipline. **`agentUsage` is mislabeled by the backend itself**: it
 * groups by `message.provider`, not by any agent identifier (there is
 * no `agent_id` column to group by) — this feature's own UI relabels
 * it "Provider usage" rather than perpetuating the backend's naming
 * mistake. `toolUsage` is keyed by raw tool UUID strings, resolved
 * against `GET /ai/tools` for display.
 */
export interface AiStatistics {
  totalConversations: number;
  totalMessages: number;
  totalToolCalls: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  estimatedCostUsd: number;
  averageLatencyMs: number;
  positiveFeedbackRate: number;
  recommendationAcceptanceRate: number;
  toolUsage: Record<string, number>;
  /** See this interface's own docstring — really a provider breakdown. */
  agentUsage: Record<string, number>;
  modelUsage: Record<string, number>;
  computedAt: string;
}

/** `PromptResponse`. */
export interface Prompt {
  id: string;
  organizationId: string;
  projectId: string | null;
  name: string;
  description: string | null;
  currentVersionNumber: string;
  enabled: boolean;
}

/** `PromptVersionResponse`. */
export interface PromptVersion {
  id: string;
  promptId: string;
  versionNumber: string;
  template: string;
  variables: string[];
  status: PromptStatusValue;
  approvedBy: string | null;
  approvedAt: string | null;
}

export interface CreatePromptInput {
  organizationId: string;
  projectId?: string;
  name: string;
  description?: string;
  template: string;
  variables?: string[];
}

export interface AddPromptVersionInput {
  template: string;
  variables?: string[];
}
