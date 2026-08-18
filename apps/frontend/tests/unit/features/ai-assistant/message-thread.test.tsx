import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MessageThread } from "@/features/ai-assistant/components/message-thread";
import { useTools } from "@/features/ai-assistant/hooks/use-catalog";
import { useMessages, useToolCalls } from "@/features/ai-assistant/hooks/use-chat";
import { useSubmitFeedback } from "@/features/ai-assistant/hooks/use-insights";
import type { Message } from "@/features/ai-assistant/types";

vi.mock("@/features/ai-assistant/hooks/use-chat", () => ({ useMessages: vi.fn(), useToolCalls: vi.fn() }));
vi.mock("@/features/ai-assistant/hooks/use-catalog", () => ({ useTools: vi.fn() }));
vi.mock("@/features/ai-assistant/hooks/use-insights", () => ({ useSubmitFeedback: vi.fn() }));

const mockedMessages = vi.mocked(useMessages);
const mockedToolCalls = vi.mocked(useToolCalls);
const mockedTools = vi.mocked(useTools);
const mockedSubmitFeedback = vi.mocked(useSubmitFeedback);

const MESSAGES: Message[] = [
  { id: "m1", conversationId: "c1", sequence: 1, role: "user", content: "Is node-42 healthy?", model: null, provider: null, promptTokens: 0, completionTokens: 0, latencyMs: null, citations: [] },
  { id: "m2", conversationId: "c1", sequence: 2, role: "assistant", content: "Yes, it's healthy.", model: "gpt-4", provider: "openai", promptTokens: 12, completionTokens: 6, latencyMs: 400, citations: [] },
];

describe("MessageThread", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function setup(overrides: Partial<ReturnType<typeof useMessages>> = {}) {
    mockedMessages.mockReturnValue({ data: MESSAGES, isLoading: false, isError: false, ...overrides } as unknown as ReturnType<typeof useMessages>);
    mockedToolCalls.mockReturnValue({ data: [] } as unknown as ReturnType<typeof useToolCalls>);
    mockedTools.mockReturnValue({ data: [] } as unknown as ReturnType<typeof useTools>);
    mockedSubmitFeedback.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useSubmitFeedback>);
  }

  it("shows a loading state while messages are loading", () => {
    setup({ isLoading: true, data: undefined });
    render(<MessageThread organizationId="org-1" conversationId="c1" />);

    expect(screen.getByRole("status", { name: "Loading messages" })).toBeInTheDocument();
  });

  it("renders messages already in sequence order without re-sorting", () => {
    setup();
    render(<MessageThread organizationId="org-1" conversationId="c1" />);

    expect(screen.getByText("Is node-42 healthy?")).toBeInTheDocument();
    expect(screen.getByText("Yes, it's healthy.")).toBeInTheDocument();
  });

  it("shows an empty state for a conversation with no messages yet", () => {
    setup({ data: [] });
    render(<MessageThread organizationId="org-1" conversationId="c1" />);

    expect(screen.getByText("No messages yet")).toBeInTheDocument();
  });

  it("shows an error state when the conversation fails to load", () => {
    setup({ isError: true, data: undefined });
    render(<MessageThread organizationId="org-1" conversationId="c1" />);

    expect(screen.getByText("This conversation could not be loaded.")).toBeInTheDocument();
  });
});
