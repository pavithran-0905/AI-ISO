import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToolCallList } from "@/features/ai-assistant/components/tool-call-list";
import { useTools } from "@/features/ai-assistant/hooks/use-catalog";
import { useToolCalls } from "@/features/ai-assistant/hooks/use-chat";
import type { Tool, ToolCall } from "@/features/ai-assistant/types";

vi.mock("@/features/ai-assistant/hooks/use-chat", () => ({ useToolCalls: vi.fn() }));
vi.mock("@/features/ai-assistant/hooks/use-catalog", () => ({ useTools: vi.fn() }));

const mockedToolCalls = vi.mocked(useToolCalls);
const mockedTools = vi.mocked(useTools);

const TOOLS: Tool[] = [
  { id: "t1", organizationId: "org-1", toolKey: "restart_service", name: "Restart service", description: "Restarts a running service.", toolKind: "automation", requiredPermission: null, isMutating: true, enabled: true },
];

function toolCall(overrides: Partial<ToolCall>): ToolCall {
  return {
    id: "tc1",
    conversationId: "c1",
    toolId: "t1",
    arguments: {},
    status: "succeeded",
    denialReason: null,
    requestedBy: "u1",
    startedAt: new Date().toISOString(),
    finishedAt: new Date().toISOString(),
    succeeded: true,
    result: {},
    errorMessage: null,
    durationMs: 420,
    ...overrides,
  };
}

describe("ToolCallList", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("resolves the tool id against the catalog and shows a real name, never the raw uuid", () => {
    mockedToolCalls.mockReturnValue({ data: [toolCall({})] } as unknown as ReturnType<typeof useToolCalls>);
    mockedTools.mockReturnValue({ data: TOOLS } as unknown as ReturnType<typeof useTools>);

    render(<ToolCallList organizationId="org-1" conversationId="c1" />);

    expect(screen.getByText("Restart service")).toBeInTheDocument();
    expect(screen.queryByText("t1")).not.toBeInTheDocument();
  });

  it("shows the denial reason for a permission-denied call", () => {
    mockedToolCalls.mockReturnValue({
      data: [toolCall({ status: "denied", denialReason: "Mutating tools were not allowed for this turn.", succeeded: null, result: null })],
    } as unknown as ReturnType<typeof useToolCalls>);
    mockedTools.mockReturnValue({ data: TOOLS } as unknown as ReturnType<typeof useTools>);

    render(<ToolCallList organizationId="org-1" conversationId="c1" />);

    expect(screen.getByText("Denied")).toBeInTheDocument();
    expect(screen.getByText("Mutating tools were not allowed for this turn.")).toBeInTheDocument();
  });

  it("shows the error message for a failed call", () => {
    mockedToolCalls.mockReturnValue({
      data: [toolCall({ status: "failed", succeeded: false, errorMessage: "Target host unreachable." })],
    } as unknown as ReturnType<typeof useToolCalls>);
    mockedTools.mockReturnValue({ data: TOOLS } as unknown as ReturnType<typeof useTools>);

    render(<ToolCallList organizationId="org-1" conversationId="c1" />);

    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Target host unreachable.")).toBeInTheDocument();
  });

  it("never renders raw arguments/result as prose", () => {
    mockedToolCalls.mockReturnValue({
      data: [toolCall({ arguments: { secret_token: "should-not-leak" }, result: { output: "should-not-render" } })],
    } as unknown as ReturnType<typeof useToolCalls>);
    mockedTools.mockReturnValue({ data: TOOLS } as unknown as ReturnType<typeof useTools>);

    render(<ToolCallList organizationId="org-1" conversationId="c1" />);

    expect(screen.queryByText(/should-not-leak/)).not.toBeInTheDocument();
    expect(screen.queryByText(/should-not-render/)).not.toBeInTheDocument();
  });

  it("renders nothing when the conversation has no tool activity", () => {
    mockedToolCalls.mockReturnValue({ data: [] } as unknown as ReturnType<typeof useToolCalls>);
    mockedTools.mockReturnValue({ data: TOOLS } as unknown as ReturnType<typeof useTools>);

    const { container } = render(<ToolCallList organizationId="org-1" conversationId="c1" />);
    expect(container).toBeEmptyDOMElement();
  });
});
