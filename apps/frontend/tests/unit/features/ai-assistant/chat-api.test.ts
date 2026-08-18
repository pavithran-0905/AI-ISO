import { afterEach, describe, expect, it, vi } from "vitest";

import { chatApi } from "@/features/ai-assistant/api/chat-api";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.resolve(body) }));
}

describe("chatApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps ChatResponse's real snake_case fields to the domain shape", async () => {
    mockFetchOnce(
      envelope({
        conversation_id: "c1",
        message_id: "m1",
        content: "It's healthy.",
        citations: [{ chunk_id: "ch1", document_id: "d1", title: "Runbook", uri: null, score: 0.9 }],
        tool_calls_made: 1,
        guardrail_findings: [],
        provider: "openai",
        model: "gpt-4",
      }),
    );

    const result = await chatApi.send({ organizationId: "org-1", message: "Is node-42 healthy?" });

    expect(result.conversationId).toBe("c1");
    expect(result.toolCallsMade).toBe(1);
    expect(result.citations).toEqual([{ chunkId: "ch1", documentId: "d1", title: "Runbook", uri: null, score: 0.9 }]);
  });

  it("sends allow_mutating_tools defaulted to false and caller_permissions defaulted to empty", async () => {
    mockFetchOnce(
      envelope({
        conversation_id: "c1",
        message_id: "m1",
        content: "ok",
        citations: [],
        tool_calls_made: 0,
        guardrail_findings: [],
        provider: null,
        model: null,
      }),
    );

    await chatApi.send({ organizationId: "org-1", message: "hello" });

    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.allow_mutating_tools).toBe(false);
    expect(body.caller_permissions).toEqual([]);
    expect(body.conversation_id).toBeUndefined();
  });

  it("builds the conversations query from mine_only, not a made-up param name", async () => {
    mockFetchOnce(envelope([]));

    await chatApi.listConversations("org-1", true);

    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(url).toContain("organization_id=org-1");
    expect(url).toContain("mine_only=true");
  });

  it("maps ToolCallResponse including a null result for a denied call", async () => {
    mockFetchOnce(
      envelope([
        {
          id: "tc1",
          conversation_id: "c1",
          tool_id: "t1",
          arguments: {},
          status: "denied",
          denial_reason: "Mutating tools were not allowed for this turn.",
          requested_by: "u1",
          started_at: null,
          finished_at: null,
          succeeded: null,
          result: null,
          error_message: null,
          duration_ms: null,
        },
      ]),
    );

    const [call] = await chatApi.listToolCalls("c1");

    expect(call.status).toBe("denied");
    expect(call.result).toBeNull();
    expect(call.denialReason).toBe("Mutating tools were not allowed for this turn.");
  });
});
