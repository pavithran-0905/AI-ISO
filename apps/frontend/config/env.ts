/**
 * Centralized environment configuration. No module should read
 * `process.env` directly outside of this file.
 *
 * `NEXT_PUBLIC_*` values MUST be read via a static `process.env.NEXT_PUBLIC_X`
 * expression (not a dynamic/bracket lookup) — Next.js inlines them into the
 * browser bundle at build time via static analysis, so a dynamic lookup like
 * `process.env[name]` silently resolves to `undefined` on the client.
 *
 * These values come from the repo-root `.env`, loaded via `dotenv-cli`
 * in this package's own `dev`/`build`/`start` scripts (`package.json`)
 * — not from a `.env` in this directory, which doesn't exist. See the
 * README's "How the repo-root `.env` reaches this app" section for why
 * that's a real `dotenv-cli` wrapper and not a `next.config.ts` hook.
 */

function withFallback(value: string | undefined, fallback: string): string {
  return value && value.length > 0 ? value : fallback;
}

/** Falls back to `services/api-gateway-service`'s own default port — the
 * real API entry point, not `services/gateway` (a separate, unrelated
 * health-only stub on 8000). See docs/frontend/architecture/authentication.md. */
export const env = {
  apiBaseUrl: withFallback(process.env.NEXT_PUBLIC_API_BASE_URL, "http://localhost:8027"),
  appEnv: withFallback(process.env.NEXT_PUBLIC_APP_ENV, "development"),
} as const;
