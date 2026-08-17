/**
 * Session state (docs/frontend Prompt 001 §13). Persisted to
 * `localStorage` since this backend is bearer-token-only — no
 * `httpOnly` cookie exists to restore a session from
 * (`services/authentication-service/app/api/auth.py` never sets
 * `Set-Cookie`). This is a deliberate, documented trade-off: an XSS
 * vulnerability could read these tokens. Do not store anything beyond
 * the two tokens here — see docs/frontend/architecture/authentication.md.
 */

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { decodeTokenClaims, isTokenExpired } from "@/auth/jwt";
import type { AuthTokens, Role, SessionStatus } from "@/auth/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  /** Decoded, NOT verified — see `@/auth/jwt`. */
  userId: string | null;
  role: Role | null;
  organizationId: string | null;
  status: SessionStatus;
  /** Why the session was last cleared — read by `AuthGuard` (Prompt 004
   * §8) to decide whether to tell the user their session expired, vs. a
   * plain sign-in prompt for a visitor who was never authenticated.
   * Deliberately not persisted (see `partialize` below): only relevant
   * for the redirect happening in this page load. */
  lastClearReason: "expired" | "manual" | null;
  setTokens: (tokens: AuthTokens) => void;
  clear: (reason?: "expired" | "manual") => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      userId: null,
      role: null,
      organizationId: null,
      status: "idle",
      lastClearReason: null,

      setTokens: (tokens) => {
        const claims = decodeTokenClaims(tokens.accessToken);
        set({
          accessToken: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          userId: claims?.sub ?? null,
          role: claims?.role ?? null,
          organizationId: claims?.organization_id ?? null,
          status: "authenticated",
          lastClearReason: null,
        });
      },

      clear: (reason = "manual") =>
        set({
          accessToken: null,
          refreshToken: null,
          userId: null,
          role: null,
          organizationId: null,
          status: "unauthenticated",
          lastClearReason: reason,
        }),
    }),
    {
      name: "aiios-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        userId: state.userId,
        role: state.role,
        organizationId: state.organizationId,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        if (state.accessToken) {
          const claims = decodeTokenClaims(state.accessToken);
          state.status = claims && !isTokenExpired(claims) ? "authenticated" : "unauthenticated";
        } else {
          state.status = "unauthenticated";
        }
      },
    },
  ),
);

/** Reads the current access token without subscribing a component to the
 * store — used by `@/api/client`'s injected token provider, which must
 * remain a plain function, not a hook. */
export function getAccessToken(): string | null {
  return useAuthStore.getState().accessToken;
}

export function getRefreshToken(): string | null {
  return useAuthStore.getState().refreshToken;
}
