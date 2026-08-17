/**
 * Auth types mirroring the REAL backend contract
 * (`services/authentication-service/app/api/auth.py`,
 * `services/authentication-service/app/api/profile.py`), confirmed by
 * direct source inspection — not invented.
 *
 * IMPORTANT, DOCUMENTED BACKEND GAP: `POST /auth/login`
 * (`services/authentication-service/app/services/authentication.py`)
 * issues access tokens via `TokenService.issue(user.id, session_id=...)`
 * with no `extra_claims` — so a real access token today carries only
 * `sub`/`iss`/`iat`/`exp`/`jti`. `role` and `organization_id` are NOT
 * currently populated at login time, even though
 * `services/api-gateway-service/app/services/auth.py` reads
 * `claims.get("role")` (singular) and `claims.get("organization_id")`
 * expecting them. Every type below treats `role`/`organizationId` as
 * nullable for this reason — do not assume they are always present. See
 * docs/frontend/architecture/authentication.md for the full note and the
 * suggested backend-side fix.
 */

/** The 6 fixed system roles (`shared_core.enums.role.Role`). A user's
 * token carries at most one of these today — not a list. */
export const ROLES = [
  "super_admin",
  "organization_admin",
  "project_admin",
  "operator",
  "viewer",
  "auditor",
] as const;

export type Role = (typeof ROLES)[number];

export interface TokenClaims {
  sub: string;
  iss: string;
  iat: number;
  exp: number;
  jti: string;
  role?: Role | null;
  organization_id?: string | null;
}

/** `TokenResponse` per `services/authentication-service/app/api/schemas/auth.py`. */
export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: "bearer";
  expiresIn: number;
}

/** `MfaChallengeResponse` — returned by `POST /auth/login` instead of
 * `AuthTokens` when the account requires a second factor. */
export interface MfaChallenge {
  mfaRequired: true;
  mfaChallengeId: string;
}

export type LoginResult = AuthTokens | MfaChallenge;

export function isMfaChallenge(result: LoginResult): result is MfaChallenge {
  return "mfaRequired" in result && result.mfaRequired === true;
}

/** `ProfileResponse` per `services/authentication-service/app/api/profile.py`. */
export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
  isEmailVerified: boolean;
  mfaEnabled: boolean;
  lastLoginAt: string | null;
  createdAt: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
  deviceFingerprint?: string;
  mfaCode?: string;
}

export type SessionStatus = "idle" | "authenticating" | "authenticated" | "unauthenticated";
