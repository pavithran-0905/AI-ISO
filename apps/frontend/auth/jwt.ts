/**
 * Client-side JWT payload decoding — for UX purposes only (reading `exp`
 * to schedule a refresh, reading `role`/`organization_id` to render a
 * badge). This performs NO signature verification: a browser cannot
 * verify an RS256 signature without the private key, and the backend
 * (`shared_core.security.jwt.decode_token`) is and remains the only
 * authoritative verifier. Never use this module to make an authorization
 * decision that matters — see docs/frontend/architecture/authorization.md.
 */

import type { TokenClaims } from "@/auth/types";

function base64UrlDecode(segment: string): string {
  const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
  return atob(padded);
}

/** Returns `null` for a malformed token rather than throwing — callers
 * treat a token that can't be decoded as absent. */
export function decodeTokenClaims(token: string): TokenClaims | null {
  const segments = token.split(".");
  if (segments.length !== 3) return null;

  try {
    const payload = JSON.parse(base64UrlDecode(segments[1])) as TokenClaims;
    return payload;
  } catch {
    return null;
  }
}

export function isTokenExpired(claims: TokenClaims, nowSeconds: number = Date.now() / 1000): boolean {
  return claims.exp <= nowSeconds;
}
