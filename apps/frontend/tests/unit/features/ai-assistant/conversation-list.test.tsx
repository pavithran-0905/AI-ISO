import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConversationList } from "@/features/ai-assistant/components/conversation-list";
import { useConversations } from "@/features/ai-assistant/hooks/use-chat";
import type { Conversation } from "@/features/ai-assistant/types";

vi.mock("@/features/ai-assistant/hooks/use-chat", () => ({ useConversations: vi.fn() }));

const mockedConversations = vi.mocked(useConversations);

const CONVERSATIONS: Conversation[] = [
  {
    id: "c1",
    organizationId: "org-1",
    projectId: null,
    sessionId: null,
    userId: "u1",
    title: "Why is node-42 unhealthy?",
    status: "active",
    startedAt: new Date().toISOString(),
    completedAt: null,
  },
  {
    id: "c2",
    organizationId: "org-1",
    projectId: null,
    sessionId: null,
    userId: "u1",
    title: "Summarize this week's incidents",
    status: "completed",
    startedAt: new Date().toISOString(),
    completedAt: new Date().toISOString(),
  },
];

function queryReturn(overrides: Record<string, unknown> = {}) {
  return { data: CONVERSATIONS, isLoading: false, isError: false, ...overrides };
}

describe("ConversationList", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("lists conversations and lets the caller select one", () => {
    mockedConversations.mockReturnValue(queryReturn() as unknown as ReturnType<typeof useConversations>);
    const onSelect = vi.fn();

    render(<ConversationList organizationId="org-1" selectedConversationId={null} onSelect={onSelect} onNewConversation={vi.fn()} />);

    expect(screen.getByText("Why is node-42 unhealthy?")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Summarize this week's incidents"));
    expect(onSelect).toHaveBeenCalledWith("c2");
  });

  it("starts a new conversation when asked", () => {
    mockedConversations.mockReturnValue(queryReturn() as unknown as ReturnType<typeof useConversations>);
    const onNewConversation = vi.fn();

    render(<ConversationList organizationId="org-1" selectedConversationId="c1" onSelect={vi.fn()} onNewConversation={onNewConversation} />);
    fireEvent.click(screen.getByRole("button", { name: /New conversation/ }));

    expect(onNewConversation).toHaveBeenCalled();
  });

  it("shows an empty state when there are no conversations yet", () => {
    mockedConversations.mockReturnValue(queryReturn({ data: [] }) as unknown as ReturnType<typeof useConversations>);

    render(<ConversationList organizationId="org-1" selectedConversationId={null} onSelect={vi.fn()} onNewConversation={vi.fn()} />);

    expect(screen.getByText("No conversations yet")).toBeInTheDocument();
  });

  it("defaults to my-conversations-only and can be toggled to the whole organization", () => {
    mockedConversations.mockReturnValue(queryReturn() as unknown as ReturnType<typeof useConversations>);

    render(<ConversationList organizationId="org-1" selectedConversationId={null} onSelect={vi.fn()} onNewConversation={vi.fn()} />);
    expect(mockedConversations).toHaveBeenLastCalledWith("org-1", true);

    fireEvent.click(screen.getByLabelText("My conversations only"));
    expect(mockedConversations).toHaveBeenLastCalledWith("org-1", false);
  });
});
