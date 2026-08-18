const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];

const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** Only ever called with a real, exact backend timestamp
 * (docs/frontend Prompt 005 §10: "Use relative time only when the
 * exact timestamp is available") — never derived or estimated. */
export function formatRelativeTime(isoTimestamp: string, now: Date = new Date()): string {
  const then = new Date(isoTimestamp);
  const diffSeconds = Math.round((then.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(diffSeconds);

  if (abs < 60) return "just now";

  for (const [unit, secondsInUnit] of UNITS) {
    if (abs >= secondsInUnit) {
      return formatter.format(Math.round(diffSeconds / secondsInUnit), unit);
    }
  }
  return formatter.format(Math.round(diffSeconds / 60), "minute");
}
