"use client";

import { Send } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import { GuardrailNotice } from "@/features/ai-assistant/components/guardrail-notice";
import { MutatingToolsToggle } from "@/features/ai-assistant/components/mutating-tools-toggle";
import { useSendMessage } from "@/features/ai-assistant/hooks/use-chat";
import { derivedCallerPermissions } from "@/features/ai-assistant/lib/caller-permissions";
import { AGENT_TYPES, type AgentTypeValue, type ChatResult } from "@/features/ai-assistant/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * The message composer (§5/§17). Enter sends, Shift+Enter inserts a
 * newline (standard chat-input convention). On failure, the typed text
 * is kept in the box rather than cleared — a failed send persists
 * nothing server-side, so "retry" is just pressing Send again with the
 * same content still there.
 */
export function Composer({
  organizationId,
  conversationId,
  initialDraft = "",
  onSent,
}: {
  organizationId: string;
  conversationId: string | null;
  /** A cross-module "Ask AI" entry point's pre-filled text (§41) — set
   * once when the composer mounts for a fresh conversation, never sent
   * automatically. */
  initialDraft?: string;
  onSent: (result: ChatResult) => void;
}) {
  const [message, setMessage] = useState(initialDraft);
  const [agentType, setAgentType] = useState<AgentTypeValue | "">("");
  const [allowMutatingTools, setAllowMutatingTools] = useState(false);
  const [lastGuardrailFindings, setLastGuardrailFindings] = useState<string[]>([]);
  const { role, can } = usePermissions();
  const sendMessage = useSendMessage();
  const canUseMutatingTools = can("execute");

  const isNewConversation = conversationId === null;

  async function handleSend() {
    const trimmed = message.trim();
    if (!trimmed || sendMessage.isPending) return;

    try {
      const result = await sendMessage.mutateAsync({
        organizationId,
        conversationId: conversationId ?? undefined,
        message: trimmed,
        agentType: isNewConversation && agentType ? agentType : undefined,
        allowMutatingTools: canUseMutatingTools && allowMutatingTools,
        callerPermissions: derivedCallerPermissions(role),
      });
      setMessage("");
      setLastGuardrailFindings(result.guardrailFindings);
      onSent(result);
    } catch (error) {
      const description = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Message could not be sent", description);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  }

  return (
    <div className="border-border flex flex-col gap-2 border-t p-3">
      <GuardrailNotice findingsCount={lastGuardrailFindings.length} />

      {isNewConversation && (
        <div className="flex items-center gap-2">
          <label htmlFor="composer-agent-type" className="text-muted-foreground shrink-0 text-xs">
            Agent
          </label>
          <Select
            id="composer-agent-type"
            value={agentType}
            onChange={(event) => setAgentType(event.target.value as AgentTypeValue | "")}
            className="h-7 max-w-[10rem] text-xs"
          >
            <option value="">Default</option>
            {AGENT_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>
      )}

      <Textarea
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask the assistant…"
        rows={3}
        aria-label="Message"
        disabled={sendMessage.isPending}
      />

      <div className="flex items-center justify-between gap-3">
        {canUseMutatingTools ? (
          <MutatingToolsToggle checked={allowMutatingTools} onChange={setAllowMutatingTools} />
        ) : (
          <span />
        )}
        <Button onClick={() => void handleSend()} loading={sendMessage.isPending} disabled={!message.trim()} className="gap-1.5">
          <Send className="size-4" aria-hidden="true" />
          Send
        </Button>
      </div>
    </div>
  );
}
