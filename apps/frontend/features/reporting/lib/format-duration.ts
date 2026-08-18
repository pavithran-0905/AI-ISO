/** Formats a duration in milliseconds (`ReportExecution.durationMs`,
 * `ReportingStatistics.averageDurationMs`) as a short human string like
 * "2.4s" or "1m 12s". Returns `null` unchanged so callers can render an
 * honest "—" instead of a fabricated "0s" when the backend hasn't
 * recorded a value yet (an execution's `durationMs` is nullable while
 * still running). */
export function formatDurationMs(ms: number | null): string | null {
  if (ms === null) return null;
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) return `${totalSeconds.toFixed(totalSeconds < 10 ? 1 : 0)}s`;

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  return `${minutes}m ${seconds}s`;
}

/** Formats a byte count (`ExportArtifact.sizeBytes`, `ArchivedReport.sizeBytes`)
 * as a short human string like "482 KB" or "3.1 MB". */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unitIndex]}`;
}
