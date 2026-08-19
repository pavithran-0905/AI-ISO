import type { StatusState } from "@/lib/status";
import type { EventSeverityValue, ServiceNodeHealthValue } from "@/features/monitoring/types";

/** `ServiceNodeHealthValue` (observability-platform-service topology)
 * → the canonical status taxonomy. */
export const SERVICE_NODE_HEALTH_TO_STATUS: Record<ServiceNodeHealthValue, StatusState> = {
  healthy: "healthy",
  degraded: "degraded",
  unhealthy: "critical",
  unknown: "unknown",
};

/** Event severity is its own taxonomy (like alert severity in
 * `features/dashboard`) — reuses the existing tone palette, not a new
 * color. */
export const EVENT_SEVERITY_TONE: Record<EventSeverityValue, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  major: "danger",
  minor: "warning",
  warning: "warning",
  info: "neutral",
};
