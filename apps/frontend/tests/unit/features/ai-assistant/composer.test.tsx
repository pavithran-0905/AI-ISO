import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Composer } from "@/features/ai-assistant/components/composer";
import { useSendMessage } from "@/features/ai-assistant/hooks/use-chat";
import type { ChatResult } from "@/features/ai-assistant/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

vi.mock("@/features/ai-assistant/hooks/use-chat", () => ({ useSendMessage: vi.fn() }));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

const mockedSendMessage = vi.mocked(useSendMessage);
const mockedPermissions = vi.mocked(usePermissions);

const RESULT: ChatResult = {
  conversationId: "c1",
  messageId: "m1",
  content: "Here you go.",
  citations: [],
  toolCallsMade: 0,
  guardrailFindings: [],
  provider: "openai",
  model: "gpt-4",
};

function mutationReturn(overrides: Record<string, unknown> = {}) {
  return { mutateAsync: vi.fn().mockResolvedValue(RESULT), isPending: false, ...overrides };
}

function setPermissions(overrides: Record<string, unknown> = {}) {
  mockedPermissions.mockReturnValue({
    role: "operator",
    can: () => true,
    isReadOnly: false,
    isAdministrative: false,
    ...overrides,
  } as unknown as ReturnType<typeof usePermissions>);
}

describe("Composer", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("sends the typed message and clears the box on success", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(RESULT);
    mockedSendMessage.mockReturnValue(mutationReturn({ mutateAsync }) as unknown as ReturnType<typeof useSendMessage>);
    setPermissions();
    const onSent = vi.fn();

    render(<Composer organizationId="org-1" conversationId={null} onSent={onSent} />);

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "What's the status of node-42?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(onSent).toHaveBeenCalledWith(RESULT));
    expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ message: "What's the status of node-42?" }));
    expect(screen.getByLabelText("Message")).toHaveValue("");
  });

  it("Enter sends, Shift+Enter inserts a newline", () => {
    const mutateAsync = vi.fn().mockResolvedValue(RESULT);
    mockedSendMessage.mockReturnValue(mutationReturn({ mutateAsync }) as unknown as ReturnType<typeof useSendMessage>);
    setPermissions();

    render(<Composer organizationId="org-1" conversationId={null} onSent={vi.fn()} />);
    const textarea = screen.getByLabelText("Message");

    fireEvent.change(textarea, { target: { value: "line one" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(mutateAsync).not.toHaveBeenCalled();

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(mutateAsync).toHaveBeenCalled();
  });

  it("shows the loading state while a send is pending", () => {
    mockedSendMessage.mockReturnValue(mutationReturn({ isPending: true }) as unknown as ReturnType<typeof useSendMessage>);
    setPermissions();

    render(<Composer organizationId="org-1" conversationId="c1" onSent={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Send" })).toHaveAttribute("aria-busy", "true");
  });

  it("keeps the typed text in the box and reports the real error on failure — the caller can just press Send again", async () => {
    const { ApiRequestError } = await import("@/api/client");
    const mutateAsync = vi.fn().mockRejectedValue(new ApiRequestError(502, "The assistant is temporarily unavailable.", "AIIOS-AI-0001", []));
    mockedSendMessage.mockReturnValue(mutationReturn({ mutateAsync }) as unknown as ReturnType<typeof useSendMessage>);
    setPermissions();

    render(<Composer organizationId="org-1" conversationId={null} onSent={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Restart the ingest worker" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(toast.danger).toHaveBeenCalledWith("Message could not be sent", "The assistant is temporarily unavailable."),
    );
    expect(screen.getByLabelText("Message")).toHaveValue("Restart the ingest worker");
  });

  it("seeds the composer from a cross-module draft without sending it", () => {
    mockedSendMessage.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useSendMessage>);
    setPermissions();

    render(<Composer organizationId="org-1" conversationId={null} initialDraft='Tell me about alert "Disk almost full" (id: a1).' onSent={vi.fn()} />);

    expect(screen.getByLabelText("Message")).toHaveValue('Tell me about alert "Disk almost full" (id: a1).');
  });

  it("hides the mutating-tools toggle for a role the coarse capability model denies execute to", () => {
    mockedSendMessage.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useSendMessage>);
    setPermissions({ role: "viewer", can: () => false, isReadOnly: true });

    render(<Composer organizationId="org-1" conversationId={null} onSent={vi.fn()} />);

    expect(screen.queryByLabelText(/Allow this assistant to take actions/)).not.toBeInTheDocument();
  });

  it("shows the agent picker only for a brand new conversation", () => {
    mockedSendMessage.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useSendMessage>);
    setPermissions();

    const { rerender } = render(<Composer organizationId="org-1" conversationId={null} onSent={vi.fn()} />);
    expect(screen.getByLabelText("Agent")).toBeInTheDocument();

    rerender(<Composer organizationId="org-1" conversationId="c1" onSent={vi.fn()} />);
    expect(screen.queryByLabelText("Agent")).not.toBeInTheDocument();
  });
});
