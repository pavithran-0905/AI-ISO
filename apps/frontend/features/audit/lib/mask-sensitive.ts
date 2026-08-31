/**
 * §24: audit payloads (`changes`, `context`) are opaque
 * `Record<string, unknown>` bags this frontend never controls the
 * shape of — none of the three services' schemas declare what keys
 * can appear. Masking by key name is the only defensible approach
 * without a backend-confirmed field allowlist; it errs toward masking
 * more than necessary rather than risking a leaked secret.
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
