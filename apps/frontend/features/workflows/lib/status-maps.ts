import type { NodeExecutionStatusValue, WorkflowInstanceStatusValue } from "@/features/workflows/types";
import type { StatusState } from "@/lib/status";

/**
 * `workflow-runtime-service`'s own 12-value status vocabulary mapped
 * onto the canonical `StatusState` taxonomy — kept entirely separate
 * from `features/automation`'s 8-value map, because the two services
 * genuinely disagree (this one has `created`/`queued`/`waiting`/
 * `checkpointed`/`retrying`/`archived`; that one has `pending` and
 * `timed_out`). Sharing one map would silently mistranslate both.
 */
export const INSTANCE_STATUS_TO_STATUS: Record<WorkflowInstanceStatusValue, StatusState> = {
  created: "pending",
  queued: "queued",
  waiting: "pending",
  running: "running",
  paused: "stopped",
  checkpointed: "stopped",
  retrying: "running",
  completed: "completed",
  cancelled: "cancelled",
  failed: "failed",
  rolled_back: "cancelled",
  archived: "unknown",
};

export const NODE_STATUS_TO_STATUS: Record<NodeExecutionStatusValue, StatusState> = {
  pending: "pending",
  running: "running",
  completed: "completed",
  failed: "failed",
  rolled_back: "cancelled",
  skipped: "unknown",
};
