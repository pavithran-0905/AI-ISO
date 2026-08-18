import { afterEach, describe, expect, it, vi } from "vitest";

import { insightsApi } from "@/features/ai-assistant/api/insights-api";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.resolve(body) }));
}

describe("insightsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps a recommendation with no timestamp field — none is invented", async () => {
    mockFetchOnce(
      envelope([
        {
          id: "r1",
          organization_id: "org-1",
          conversation_id: null,
          recommendation_type: "automation",
          title: "Automate certificate rotation",
          body: "…",
          rationale: null,
          citations: [],
          confidence: 0.75,
          status: "proposed",
          decided_by: null,
        },
      ]),
    );

    const [recommendation] = await insightsApi.listRecommendations("org-1");

    expect(recommendation.status).toBe("proposed");
    expect(Object.keys(recommendation)).not.toContain("createdAt");
  });

  it("posts accept=true to the decide endpoint at the right path", async () => {
    mockFetchOnce(
      envelope({
        id: "r1",
        organization_id: "org-1",
        conversation_id: null,
        recommendation_type: "automation",
        title: "t",
        body: "b",
        rationale: null,
        citations: [],
        confidence: null,
        status: "accepted",
        decided_by: "u1",
      }),
    );

    await insightsApi.decideRecommendation("r1", true);

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/ai/recommendations/r1/decide");
    expect(JSON.parse(init.body as string)).toEqual({ accept: true });
  });

  it("maps AiReportResponse including generatedAt — the one real timestamp in this feature's lists", async () => {
    mockFetchOnce(
      envelope([
        {
          id: "rep1",
          organization_id: "org-1",
          conversation_id: null,
          report_type: "operational",
          title: "Weekly operational summary",
          body: "…",
          parameters: {},
          citations: [],
          generated_by: "u1",
          generated_at: "2026-08-01T00:00:00Z",
        },
      ]),
    );

    const [report] = await insightsApi.listReports("org-1");

    expect(report.generatedAt).toBe("2026-08-01T00:00:00Z");
  });

  it("passes recompute=true through to the statistics query only when asked", async () => {
    mockFetchOnce(
      envelope({
        total_conversations: 1,
        total_messages: 2,
        total_tool_calls: 0,
        total_prompt_tokens: 10,
        total_completion_tokens: 5,
        estimated_cost_usd: 0.01,
        average_latency_ms: 300,
        positive_feedback_rate: 1,
        recommendation_acceptance_rate: 0,
        tool_usage: {},
        agent_usage: { openai: 1 },
        model_usage: { "gpt-4": 1 },
        computed_at: "2026-08-01T00:00:00Z",
      }),
    );

    await insightsApi.statistics("org-1", true);

    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(url).toContain("recompute=true");
  });
});
