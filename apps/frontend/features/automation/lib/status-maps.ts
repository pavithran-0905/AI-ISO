import type { StatusTone } from "@/components/feedback/status-badge";
import type { ExecutionStatusValue, JobStatusValue, LogLevelValue } from "@/features/automation/types";
import type { StatusState } from "@/lib/status";

/**
 * The frontend semantic mapping layer §8 asks for. `automation-service`'s
 * `ExecutionStatus` is one of three genuinely different execution
 * vocabularies in this platform (`workflow-runtime-service` and
 * `scheduler-service` each have their own, with different members) —
 * each is mapped onto the canonical `StatusState` taxonomy
 * (`@/lib/status`) independently, and they are never conflated.
 */
export const EXECUTION_STATUS_TO_STATUS: Record<ExecutionStatusValue, StatusState> = {
  pending: "pending",
  running: "running",
  paused: "stopped",
  completed: "completed",
  failed: "failed",
  cancelled: "cancelled",
  timed_out: "failed",
  rolled_back: "cancelled",
};

export const JOB_STATUS_TONE: Record<JobStatusValue, StatusTone> = {
  draft: "neutral",
  active: "success",
  disabled: "stopped",
  archived: "neutral",
};

export const LOG_LEVEL_TONE: Record<LogLevelValue, StatusTone> = {
  debug: "neutral",
  info: "info",
  warning: "warning",
  error: "danger",
};
