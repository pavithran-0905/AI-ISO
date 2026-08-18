import type { StatusTone } from "@/components/feedback/status-badge";
import { ALERT_SEVERITIES, type AlertSeverity } from "@/features/alerting/types";

/** Alert severity is its own taxonomy, distinct from the operational
 * `StatusState` vocabulary (`@/lib/status`) — reuses the same 10-tone
 * palette rather than inventing new colors (docs/frontend Prompt 002
 * §18), just mapped for a different axis. Matches
 * `features/dashboard/components/attention-required-section.tsx`'s own
 * mapping exactly — kept in one place now that both consume it. */
export const SEVERITY_TONE: Record<AlertSeverity, StatusTone> = {
  critical: "danger",
  high: "warning",
  medium: "warning",
  low: "info",
  info: "neutral",
};

export const SEVERITY_RANK: Record<AlertSeverity, number> = Object.fromEntries(
  ALERT_SEVERITIES.map((severity, index) => [severity, index]),
) as Record<AlertSeverity, number>;

export const SEVERITY_LABEL: Record<AlertSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Informational",
};
