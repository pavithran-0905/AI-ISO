/**
 * The canonical status taxonomy (docs/frontend Prompt 002 §18). One
 * table maps every named operational state a feature can report onto
 * one of the 10 status *tones* defined in `app/globals.css` (§5) — no
 * future feature module may invent its own status color or icon; it
 * looks a state up here instead.
 *
 * Two axes, deliberately kept distinct: a *tone* (`success`/`warning`/
 * `danger`/`info`/`neutral`/`pending`/`running`/`stopped`/`degraded`/
 * `unknown`) is a CSS-level color token; a *named state* (`Healthy`,
 * `Queued`, `Maintenance`, ...) is a business-level vocabulary word
 * that resolves to exactly one tone. Two named states can share a tone
 * (`Healthy` and `Completed` are both genuinely positive outcomes) —
 * that's a feature of this design, not a gap.
 */

import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  HelpCircle,
  ListOrdered,
  type LucideIcon,
  Square,
  TrendingDown,
  Wrench,
  XCircle,
} from "lucide-react";

export const STATUS_TONES = [
  "success",
  "warning",
  "danger",
  "info",
  "neutral",
  "pending",
  "running",
  "stopped",
  "degraded",
  "unknown",
] as const;

export type StatusTone = (typeof STATUS_TONES)[number];

export const STATUS_STATES = [
  "healthy",
  "warning",
  "critical",
  "failed",
  "running",
  "stopped",
  "pending",
  "queued",
  "completed",
  "cancelled",
  "unknown",
  "degraded",
  "maintenance",
] as const;

export type StatusState = (typeof STATUS_STATES)[number];

interface StatusDefinition {
  tone: StatusTone;
  label: string;
  icon: LucideIcon;
}

export const STATUS_TAXONOMY: Record<StatusState, StatusDefinition> = {
  healthy: { tone: "success", label: "Healthy", icon: CheckCircle2 },
  warning: { tone: "warning", label: "Warning", icon: AlertTriangle },
  critical: { tone: "danger", label: "Critical", icon: AlertOctagon },
  failed: { tone: "danger", label: "Failed", icon: XCircle },
  running: { tone: "running", label: "Running", icon: Activity },
  stopped: { tone: "stopped", label: "Stopped", icon: Square },
  pending: { tone: "pending", label: "Pending", icon: Clock },
  queued: { tone: "pending", label: "Queued", icon: ListOrdered },
  completed: { tone: "success", label: "Completed", icon: CheckCircle2 },
  cancelled: { tone: "neutral", label: "Cancelled", icon: Ban },
  unknown: { tone: "unknown", label: "Unknown", icon: HelpCircle },
  degraded: { tone: "degraded", label: "Degraded", icon: TrendingDown },
  maintenance: { tone: "neutral", label: "Maintenance", icon: Wrench },
};

export function resolveStatus(state: StatusState): StatusDefinition {
  return STATUS_TAXONOMY[state];
}
