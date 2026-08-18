import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageItem } from "@/features/ai-assistant/components/message-item";
import { useSubmitFeedback } from "@/features/ai-assistant/hooks/use-insights";
import type { Message } from "@/features/ai-assistant/types";

vi.mock("@/features/ai-assistant/hooks/use-insights", () => ({ useSubmitFeedback: vi.fn() }));

vi.mocked(useSubmitFeedback).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useSubmitFeedback>);

function message(overrides: Partial<Message>): Message {
  return {
    id: "m1",
    conversationId: "c1",
    sequence: 1,
    role: "user",
    content: "What is the status of node-42?",
    model: null,
    provider: null,
    promptTokens: 0,
    completionTokens: 0,
    latencyMs: null,
    citations: [],
    ...overrides,
  };
}

describe("MessageItem", () => {
  it("renders a user message without feedback controls", () => {
    render(<MessageItem organizationId="org-1" message={message({ role: "user" })} />);

    expect(screen.getByText("What is the status of node-42?")).toBeInTheDocument();
    expect(screen.queryByLabelText("Helpful")).not.toBeInTheDocument();
  });

  it("renders an assistant message with feedback controls and provider/model attribution", () => {
    render(
      <MessageItem
        organizationId="org-1"
        message={message({ role: "assistant", content: "It is healthy.", provider: "openai", model: "gpt-4" })}
      />,
    );

    expect(screen.getByText("It is healthy.")).toBeInTheDocument();
    expect(screen.getByLabelText("Helpful")).toBeInTheDocument();
    expect(screen.getByText(/openai/)).toBeInTheDocument();
    expect(screen.getByText(/gpt-4/)).toBeInTheDocument();
  });

  it("preserves real newlines from plain-text content without interpreting markup", () => {
    const { container } = render(<MessageItem organizationId="org-1" message={message({ role: "assistant", content: "Step 1\nStep 2" })} />);

    const paragraph = container.querySelector("p.whitespace-pre-wrap");
    expect(paragraph?.textContent).toBe("Step 1\nStep 2");
  });
});
