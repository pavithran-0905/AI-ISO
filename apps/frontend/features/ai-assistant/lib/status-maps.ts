import type { StatusTone } from "@/components/feedback/status-badge";
import type {
  ConversationStatusValue,
  PromptStatusValue,
  RecommendationStatusValue,
  ToolCallStatusValue,
} from "@/features/ai-assistant/types";
import type { StatusState } from "@/lib/status";

/**
 * `Conversation.status` genuinely is an operational lifecycle state
 * (mirroring `ExecutionStatusValue`'s own treatment in
 * `@/features/automation/lib/status-maps.ts`), so it maps onto the
 * canonical `StatusState` taxonomy for use with `StatusIndicator`. Note
 * only `active` is ever reached in practice today — see this file's
 * own callers and `docs/frontend/backend-v1-integration-limitations.md`.
 */
export const CONVERSATION_STATUS_TO_STATUS: Record<ConversationStatusValue, StatusState> = {
  active: "running",
  completed: "completed",
  failed: "failed",
  expired: "stopped",
};

/**
 * `ToolCallStatusValue`/`RecommendationStatusValue`/`PromptStatusValue`
 * are decision/permission vocabularies, not operational states — like
 * `LOG_LEVEL_TONE` in automation's own status-maps, they map directly
 * to a tone rather than forcing an ill-fitting `StatusState` (there is
 * no canonical "Denied" or "Applied" state).
 */
export const TOOL_CALL_STATUS_TONE: Record<ToolCallStatusValue, StatusTone> = {
  pending: "pending",
  running: "running",
  succeeded: "success",
  failed: "danger",
  denied: "warning",
};

export const RECOMMENDATION_STATUS_TONE: Record<RecommendationStatusValue, StatusTone> = {
  proposed: "pending",
  accepted: "success",
  rejected: "danger",
  applied: "success",
};

export const PROMPT_STATUS_TONE: Record<PromptStatusValue, StatusTone> = {
  draft: "neutral",
  approved: "success",
  archived: "neutral",
};
