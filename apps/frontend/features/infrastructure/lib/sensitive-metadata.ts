/**
 * `Asset.metadata` is a genuinely free-form `dict[str, Any]` (confirmed
 * by source inspection — no dedicated credential/secret field or model
 * column exists anywhere in `inventory-service`, but nothing stops a
 * caller from putting one in this dict either). §17 forbids ever
 * rendering a password/API key/private key/token/secret value — this
 * is a defensive, name-based mask applied purely in the presentation
 * layer, not a backend guarantee: a key whose name merely *looks*
 * sensitive is masked, regardless of what it actually holds.
 */
const SENSITIVE_KEY_PATTERN = /password|secret|token|api[_-]?key|private[_-]?key|credential/i;

export function isSensitiveMetadataKey(key: string): boolean {
  return SENSITIVE_KEY_PATTERN.test(key);
}

export function maskMetadataValue(key: string, value: unknown): string {
  if (isSensitiveMetadataKey(key)) return "••••••••";
  return typeof value === "string" ? value : JSON.stringify(value);
}
