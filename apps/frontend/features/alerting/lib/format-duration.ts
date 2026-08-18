/** Formats a duration in seconds (e.g. `AlertStatistics.mttaSeconds`) as
 * a short human string like "2h 15m" or "45s". Returns `null` unchanged
 * so callers can render an honest "—" instead of a fabricated "0s" when
 * the backend hasn't computed a value yet (all three duration fields on
 * `AlertStatistics` are nullable). */
export function formatDurationSeconds(seconds: number | null): string | null {
  if (seconds === null) return null;
  if (seconds < 60) return `${Math.round(seconds)}s`;

  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) return `${minutes}m`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}
