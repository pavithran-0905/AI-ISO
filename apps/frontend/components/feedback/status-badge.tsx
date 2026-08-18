import type { LucideIcon } from "lucide-react";

import { cn } from "@/utils/cn";

/** The full status tone set (§5) — `success`/`warning`/`danger`/
 * `neutral` predate this prompt and stay first for backward
 * compatibility with existing callers (e.g.
 * `features/dashboard/components/gateway-liveness-card.tsx`). */
export type StatusTone =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "info"
  | "pending"
  | "running"
  | "stopped"
  | "degraded"
  | "unknown";

const TONE_CLASSES: Record<StatusTone, string> = {
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  danger: "bg-danger/15 text-danger",
  neutral: "bg-muted text-muted-foreground",
  info: "bg-info/15 text-info",
  pending: "bg-pending/15 text-pending-foreground dark:text-pending",
  running: "bg-running/15 text-running",
  stopped: "bg-stopped/15 text-stopped-foreground dark:text-stopped",
  degraded: "bg-degraded/15 text-degraded",
  unknown: "bg-unknown/25 text-unknown-foreground",
};

export interface StatusBadgeProps {
  tone: StatusTone;
  label: string;
  /** An icon per §5 ("every status presentation must also support:
   * icon, label, text") — optional so the plain dot-+-label look
   * already used by the dashboard keeps working unchanged. */
  icon?: LucideIcon;
  className?: string;
}

/** The generic tone+label primitive. For a named operational state
 * (`"healthy"`, `"queued"`, ...) use `StatusIndicator`
 * (`components/data-display/status-indicator.tsx`) instead, which
 * resolves the canonical taxonomy (`@/lib/status`) to this component's
 * props — don't hand-pick a tone/icon/label for a named state at the
 * call site. */
export function StatusBadge({ tone, label, icon: Icon, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {Icon ? (
        <Icon className="size-3" aria-hidden="true" />
      ) : (
        <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      )}
      {label}
    </span>
  );
}
