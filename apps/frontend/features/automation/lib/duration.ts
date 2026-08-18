import type { AutomationExecution } from "@/features/automation/types";

/** `AutomationExecutionResponse` has no `duration` field, so it's
 * computed here from the two real timestamps. Returns `null` — not
 * zero — whenever the run hasn't both started and finished, so callers
 * render an honest "—" instead of a fabricated "0s". */
export function executionDurationMs(execution: AutomationExecution): number | null {
  if (!execution.startedAt || !execution.completedAt) return null;
  return new Date(execution.completedAt).getTime() - new Date(execution.startedAt).getTime();
}

/** Formats a millisecond duration as a short human string ("2.4s",
 * "1m 12s", "1h 4m"). */
export function formatDurationMs(ms: number | null): string | null {
  if (ms === null) return null;
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) return `${totalSeconds.toFixed(totalSeconds < 10 ? 1 : 0)}s`;

  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) return `${totalMinutes}m ${Math.round(totalSeconds % 60)}s`;

  const hours = Math.floor(totalMinutes / 60);
  return `${hours}h ${totalMinutes % 60}m`;
}

/** Formats a duration in whole seconds (`AutomationStatistics.averageRuntimeSeconds`). */
export function formatDurationSeconds(seconds: number): string {
  return formatDurationMs(seconds * 1000) ?? "—";
}
