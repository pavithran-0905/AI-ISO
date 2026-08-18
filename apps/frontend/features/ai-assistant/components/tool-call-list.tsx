"use client";

import { useMemo } from "react";

import { StatusBadge } from "@/components/feedback/status-badge";
import { useTools } from "@/features/ai-assistant/hooks/use-catalog";
import { useToolCalls } from "@/features/ai-assistant/hooks/use-chat";
import { TOOL_CALL_STATUS_TONE } from "@/features/ai-assistant/lib/status-maps";
import type { ToolCallStatusValue } from "@/features/ai-assistant/types";

const STATUS_LABEL: Record<ToolCallStatusValue, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  denied: "Denied",
};

/**
 * A conversation's tool activity, shown as its own section below the
 * transcript rather than interleaved into it — `ToolCallResponse` has
 * no `messageId`, so the backend gives no way to say which assistant
 * message a given call actually supported, only which conversation it
 * belongs to (see `ToolCall`'s own docstring). Never renders raw
 * `arguments`/`result` as prose — they're real tool payloads, shown in
 * a `<pre>` only when a user explicitly wants to inspect one.
 */
export function ToolCallList({ organizationId, conversationId }: { organizationId: string; conversationId: string }) {
  const toolCallsQuery = useToolCalls(conversationId);
  const toolsQuery = useTools(organizationId);

  const toolNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const tool of toolsQuery.data ?? []) map.set(tool.id, tool.name);
    return map;
  }, [toolsQuery.data]);

  if (!toolCallsQuery.data || toolCallsQuery.data.length === 0) return null;

  return (
    <div className="border-border flex flex-col gap-2 rounded-md border p-3">
      <p className="text-sm font-medium">Tool activity</p>
      <ul className="flex flex-col gap-2">
        {toolCallsQuery.data.map((call) => (
          <li key={call.id} className="flex flex-col gap-1 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{toolNameById.get(call.toolId) ?? "Unknown tool"}</span>
              <StatusBadge tone={TOOL_CALL_STATUS_TONE[call.status]} label={STATUS_LABEL[call.status]} />
            </div>
            {call.status === "denied" && call.denialReason && (
              <p className="text-muted-foreground text-xs">{call.denialReason}</p>
            )}
            {call.status === "failed" && call.errorMessage && (
              <p className="text-danger text-xs">{call.errorMessage}</p>
            )}
            {call.status === "succeeded" && call.durationMs !== null && (
              <p className="text-muted-foreground text-xs">Completed in {Math.round(call.durationMs)}ms</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
