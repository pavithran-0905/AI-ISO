/**
 * Auth feature-level API functions — the "Feature API Function" layer
 * (docs/frontend Prompt 001 §10) for the auth feature specifically,
 * calling through the shared `@/api/client`. Paths mirror
 * `services/authentication-service/app/api/auth.py` and `profile.py`
 * exactly; nothing here is invented.
 */

import { apiClient } from "@/api/client";
import type { AuthTokens, AuthUser, LoginCredentials, LoginResult, MfaChallenge } from "@/auth/types";

interface TokenResponseBody {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

interface MfaChallengeResponseBody {
  mfa_required: true;
  mfa_challenge_id: string;
}

function toAuthTokens(body: TokenResponseBody): AuthTokens {
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    tokenType: body.token_type,
    expiresIn: body.expires_in,
  };
}

function toMfaChallenge(body: MfaChallengeResponseBody): MfaChallenge {
  return { mfaRequired: true, mfaChallengeId: body.mfa_challenge_id };
}

function isMfaChallengeBody(
  body: TokenResponseBody | MfaChallengeResponseBody,
): body is MfaChallengeResponseBody {
  return "mfa_required" in body;
}

export const authApi = {
  async login(credentials: LoginCredentials): Promise<LoginResult> {
    const body = await apiClient.post<TokenResponseBody | MfaChallengeResponseBody>(
      "/auth/login",
      {
        email: credentials.email,
        password: credentials.password,
        remember_me: credentials.rememberMe ?? false,
        device_fingerprint: credentials.deviceFingerprint,
        mfa_code: credentials.mfaCode,
      },
      { skipAuth: true, skipRetry: true },
    );
    return isMfaChallengeBody(body) ? toMfaChallenge(body) : toAuthTokens(body);
  },

  async refresh(refreshToken: string): Promise<AuthTokens> {
    const body = await apiClient.post<TokenResponseBody>(
      "/auth/refresh",
      { refresh_token: refreshToken },
      { skipAuth: true, skipRetry: true },
    );
    return toAuthTokens(body);
  },

  async logout(refreshToken: string | null): Promise<void> {
    await apiClient.post<{ success: boolean }>(
      "/auth/logout",
      refreshToken ? { refresh_token: refreshToken } : {},
      { skipRetry: true },
    );
  },

  async fetchProfile(): Promise<AuthUser> {
    interface ProfileResponseBody {
      id: string;
      email: string;
      display_name: string;
      is_email_verified: boolean;
      mfa_enabled: boolean;
      last_login_at: string | null;
      created_at: string;
    }
    const body = await apiClient.get<ProfileResponseBody>("/auth/profile");
    return {
      id: body.id,
      email: body.email,
      displayName: body.display_name,
      isEmailVerified: body.is_email_verified,
      mfaEnabled: body.mfa_enabled,
      lastLoginAt: body.last_login_at,
      createdAt: body.created_at,
    };
  },
};
