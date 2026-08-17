import { StatusBadge } from "@/components/feedback/status-badge";
import { resolveStatus, type StatusState } from "@/lib/status";

/**
 * Renders a named operational state (`"healthy"`, `"queued"`,
 * `"maintenance"`, ...) via the canonical taxonomy
 * (`@/lib/status`) — the component every future feature should reach
 * for instead of picking a `StatusBadge` tone/icon/label by hand,
 * which is exactly how "every module invents its own status colour"
 * (docs/frontend Prompt 002 §18) happens.
 */
export function StatusIndicator({
  state,
  label,
  className,
}: {
  state: StatusState;
  /** Overrides the taxonomy's own display label — for a feature that
   * needs, say, a localized or more specific label ("3/4 nodes
   * healthy") while keeping the canonical tone and icon. */
  label?: string;
  className?: string;
}) {
  const definition = resolveStatus(state);
  return (
    <StatusBadge tone={definition.tone} label={label ?? definition.label} icon={definition.icon} className={className} />
  );
}
