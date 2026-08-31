/**
 * Shared by every feature that renders an opaque, backend-defined
 * `Record<string, unknown>` payload this frontend doesn't control the
 * shape of (Prompt 015's audit `changes`/`context`, Prompt 016's
 * notification `metadata`) — masking by key name is the only
 * defensible approach without a backend-confirmed field allowlist; it
 * errs toward masking more than strictly necessary rather than risking
 * a leaked secret. Promoted here from `features/audit/lib/mask-sensitive.ts`
 * once a second feature needed the identical logic.
 */
const SENSITIVE_KEY_PATTERN = /password|token|secret|api[_-]?key|private[_-]?key|credential/i;

const MASK = "••••••••";

export function maskSensitiveEntries(value: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(value)) {
    if (SENSITIVE_KEY_PATTERN.test(key)) {
      result[key] = MASK;
    } else if (entry !== null && typeof entry === "object" && !Array.isArray(entry)) {
      result[key] = maskSensitiveEntries(entry as Record<string, unknown>);
    } else {
      result[key] = entry;
    }
  }
  return result;
}
