/**
 * `services/ai-assistant-service/app/api/insights.py` — confirmed by
 * source inspection. Covers recommendations, AI reports, feedback,
 * memory, and statistics.
 */

import { apiClient } from "@/api/client";
import type {
  AiReport,
  AiReportTypeValue,
  AiStatistics,
  Citation,
  FeedbackRatingValue,
  GenerateAiReportInput,
  GenerateRecommendationInput,
  MemoryEntry,
  MemoryScopeValue,
  Recommendation,
  RecommendationStatusValue,
  RecommendationTypeValue,
} from "@/features/ai-assistant/types";

interface CitationBody {
  chunk_id: string;
  document_id: string;
  title: string;
  uri: string | null;
  score: number;
}

interface RecommendationResponseBody {
  id: string;
  organization_id: string;
  conversation_id: string | null;
  recommendation_type: RecommendationTypeValue;
  title: string;
  body: string;
  rationale: string | null;
  citations: CitationBody[];
  confidence: number | null;
  status: RecommendationStatusValue;
  decided_by: string | null;
}

interface AiReportResponseBody {
  id: string;
  organization_id: string;
  conversation_id: string | null;
  report_type: AiReportTypeValue;
  title: string;
  body: string;
  parameters: Record<string, unknown>;
  citations: CitationBody[];
  generated_by: string | null;
  generated_at: string;
}

interface MemoryResponseBody {
  id: string;
  scope: MemoryScopeValue;
  scope_reference: string;
  key: string;
  value: string;
  importance: number;
  expires_at: string | null;
}

interface StatisticsResponseBody {
  total_conversations: number;
  total_messages: number;
  total_tool_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  estimated_cost_usd: number;
  average_latency_ms: number;
  positive_feedback_rate: number;
  recommendation_acceptance_rate: number;
  tool_usage: Record<string, number>;
  agent_usage: Record<string, number>;
  model_usage: Record<string, number>;
  computed_at: string;
}

function toCitation(body: CitationBody): Citation {
  return { chunkId: body.chunk_id, documentId: body.document_id, title: body.title, uri: body.uri, score: body.score };
}

function toRecommendation(body: RecommendationResponseBody): Recommendation {
  return {
    id: body.id,
    organizationId: body.organization_id,
    conversationId: body.conversation_id,
    recommendationType: body.recommendation_type,
    title: body.title,
    body: body.body,
    rationale: body.rationale,
    citations: body.citations.map(toCitation),
    confidence: body.confidence,
    status: body.status,
    decidedBy: body.decided_by,
  };
}

function toAiReport(body: AiReportResponseBody): AiReport {
  return {
    id: body.id,
    organizationId: body.organization_id,
    conversationId: body.conversation_id,
    reportType: body.report_type,
    title: body.title,
    body: body.body,
    parameters: body.parameters,
    citations: body.citations.map(toCitation),
    generatedBy: body.generated_by,
    generatedAt: body.generated_at,
  };
}

function toMemoryEntry(body: MemoryResponseBody): MemoryEntry {
  return {
    id: body.id,
    scope: body.scope,
    scopeReference: body.scope_reference,
    key: body.key,
    value: body.value,
    importance: body.importance,
    expiresAt: body.expires_at,
  };
}

export const insightsApi = {
  async generateRecommendation(input: GenerateRecommendationInput): Promise<Recommendation> {
    const body = await apiClient.post<RecommendationResponseBody>("/ai/recommendations", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      conversation_id: input.conversationId,
      recommendation_type: input.recommendationType,
      subject: input.subject,
    });
    return toRecommendation(body);
  },

  async listRecommendations(organizationId: string, conversationId?: string): Promise<Recommendation[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (conversationId) query.set("conversation_id", conversationId);
    const body = await apiClient.get<RecommendationResponseBody[]>(`/ai/recommendations?${query.toString()}`);
    return body.map(toRecommendation);
  },

  async decideRecommendation(recommendationId: string, accept: boolean): Promise<Recommendation> {
    const body = await apiClient.post<RecommendationResponseBody>(
      `/ai/recommendations/${encodeURIComponent(recommendationId)}/decide`,
      { accept },
    );
    return toRecommendation(body);
  },

  async generateReport(input: GenerateAiReportInput): Promise<AiReport> {
    const body = await apiClient.post<AiReportResponseBody>("/ai/reports", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      conversation_id: input.conversationId,
      report_type: input.reportType,
      subject: input.subject,
      parameters: input.parameters ?? {},
    });
    return toAiReport(body);
  },

  /** Returns each report in full (title/body/citations) — there is no
   * `GET /ai/reports/{id}`, but none is needed since the list endpoint
   * never truncates. */
  async listReports(organizationId: string, reportType?: AiReportTypeValue): Promise<AiReport[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (reportType) query.set("report_type", reportType);
    const body = await apiClient.get<AiReportResponseBody[]>(`/ai/reports?${query.toString()}`);
    return body.map(toAiReport);
  },

  async submitFeedback(organizationId: string, messageId: string, rating: FeedbackRatingValue, comment?: string): Promise<void> {
    await apiClient.post<unknown>("/ai/feedback", {
      organization_id: organizationId,
      message_id: messageId,
      rating,
      comment,
    });
  },

  async listMemory(organizationId: string): Promise<MemoryEntry[]> {
    const body = await apiClient.get<MemoryResponseBody[]>(`/ai/memory?organization_id=${encodeURIComponent(organizationId)}`);
    return body.map(toMemoryEntry);
  },

  async statistics(organizationId: string, recompute = false): Promise<AiStatistics> {
    const query = new URLSearchParams({ organization_id: organizationId, recompute: String(recompute) });
    const body = await apiClient.get<StatisticsResponseBody>(`/ai/statistics?${query.toString()}`);
    return {
      totalConversations: body.total_conversations,
      totalMessages: body.total_messages,
      totalToolCalls: body.total_tool_calls,
      totalPromptTokens: body.total_prompt_tokens,
      totalCompletionTokens: body.total_completion_tokens,
      estimatedCostUsd: body.estimated_cost_usd,
      averageLatencyMs: body.average_latency_ms,
      positiveFeedbackRate: body.positive_feedback_rate,
      recommendationAcceptanceRate: body.recommendation_acceptance_rate,
      toolUsage: body.tool_usage,
      agentUsage: body.agent_usage,
      modelUsage: body.model_usage,
      computedAt: body.computed_at,
    };
  },
};
