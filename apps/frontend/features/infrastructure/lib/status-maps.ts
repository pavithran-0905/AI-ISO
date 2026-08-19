import type { StatusTone } from "@/components/feedback/status-badge";
import type {
  AssetHealthValue,
  AssetStatusValue,
  CriticalityValue,
  ImportExportJobStatusValue,
  LifecycleStateValue,
} from "@/features/infrastructure/types";
import type { StatusState } from "@/lib/status";

/** `AssetHealthValue` — a genuine operational-health concept, so it
 * maps onto the canonical `StatusState` taxonomy for use with
 * `StatusIndicator`. Carried over unchanged from
 * `features/monitoring/lib/status-maps.ts#ASSET_HEALTH_TO_STATUS`,
 * which this feature supersedes. */
export const ASSET_HEALTH_TO_STATUS: Record<AssetHealthValue, StatusState> = {
  healthy: "healthy",
  warning: "warning",
  critical: "critical",
  unknown: "unknown",
  offline: "stopped",
  unreachable: "failed",
};

/** `AssetStatusValue`/`LifecycleStateValue`/`CriticalityValue` are
 * inventory/governance vocabularies, not operational states — like
 * `features/automation/lib/status-maps.ts#JOB_STATUS_TONE`, each maps
 * directly to a tone rather than forcing an ill-fitting `StatusState`. */
export const ASSET_STATUS_TONE: Record<AssetStatusValue, StatusTone> = {
  discovered: "neutral",
  registered: "info",
  managed: "success",
  unmanaged: "warning",
  provisioning: "pending",
  maintenance: "warning",
  retired: "neutral",
  archived: "neutral",
  deleted: "danger",
};

export const LIFECYCLE_STATE_TONE: Record<LifecycleStateValue, StatusTone> = {
  planned: "neutral",
  provisioning: "pending",
  operational: "success",
  maintenance: "warning",
  retired: "neutral",
  disposed: "danger",
  archived: "neutral",
};

export const CRITICALITY_TONE: Record<CriticalityValue, StatusTone> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
};

/** `shared_core.enums.job_status.JobStatus`, as used by export/import
 * jobs — a queue-lifecycle vocabulary, also tone-only. */
export const IMPORT_EXPORT_JOB_STATUS_TONE: Record<ImportExportJobStatusValue, StatusTone> = {
  registered: "neutral",
  scheduled: "pending",
  pending: "pending",
  queued: "pending",
  running: "running",
  completed: "success",
  failed: "danger",
  retrying: "warning",
  paused: "neutral",
  cancelled: "neutral",
  timed_out: "danger",
  expired: "neutral",
  archived: "neutral",
};
