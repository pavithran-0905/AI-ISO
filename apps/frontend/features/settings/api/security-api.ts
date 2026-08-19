/**
 * `services/authentication-service` — MFA, API keys, devices, sessions.
 * No authenticated "change password" route exists (confirmed absent —
 * only the anonymous forgot/reset-password email flow) — see
 * `requestPasswordReset`'s own docstring.
 */

import { apiClient } from "@/api/client";
import type {
  ApiKeyCreated,
  ApiKeySummary,
  CreateApiKeyInput,
  DeviceSummary,
  MfaEnableResult,
  SessionSummary,
} from "@/features/settings/types";

interface MfaEnableResponseBody {
  secret: string;
  otpauth_uri: string;
  recovery_codes: string[];
}

interface ApiKeySummaryBody {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

function toApiKeySummary(body: ApiKeySummaryBody): ApiKeySummary {
  return {
    id: body.id,
    name: body.name,
    keyPrefix: body.key_prefix,
    scopes: body.scopes,
    expiresAt: body.expires_at,
    lastUsedAt: body.last_used_at,
    revokedAt: body.revoked_at,
  };
}

interface DeviceSummaryBody {
  id: string;
  device_name: string | null;
  browser: string | null;
  operating_system: string | null;
  ip_address: string | null;
  location: string | null;
  last_login_at: string | null;
  is_trusted: boolean;
  trusted_until: string | null;
}

interface SessionSummaryBody {
  id: string;
  session_id: string;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  last_active_at: string;
  expires_at: string;
}

export const securityApi = {
  async enableMfa(): Promise<MfaEnableResult> {
    const body = await apiClient.post<MfaEnableResponseBody>("/auth/mfa/enable");
    return { secret: body.secret, otpauthUri: body.otpauth_uri, recoveryCodes: body.recovery_codes };
  },

  async verifyMfa(code: string): Promise<void> {
    await apiClient.post("/auth/mfa/verify", { code });
  },

  async disableMfa(code: string): Promise<void> {
    await apiClient.post("/auth/mfa/disable", { code });
  },

  /** No authenticated "change password with current password" route
   * exists on this backend (confirmed absent — only
   * `POST /auth/forgot-password`, an anonymous, email-token-based
   * flow). This sends a reset link to the caller's own known email —
   * the only real password-change mechanism available. */
  async requestPasswordReset(email: string): Promise<void> {
    await apiClient.post("/auth/forgot-password", { email });
  },

  async listApiKeys(): Promise<ApiKeySummary[]> {
    const body = await apiClient.get<ApiKeySummaryBody[]>("/auth/apikeys");
    return body.map(toApiKeySummary);
  },

  /** The raw key is returned once, here, and never again. */
  async createApiKey(input: CreateApiKeyInput): Promise<ApiKeyCreated> {
    const body = await apiClient.post<ApiKeySummaryBody & { raw_key: string }>("/auth/apikeys", {
      name: input.name,
      scopes: input.scopes,
      expires_in_days: input.expiresInDays,
    });
    return { ...toApiKeySummary(body), rawKey: body.raw_key };
  },

  async revokeApiKey(apiKeyId: string): Promise<void> {
    await apiClient.delete(`/auth/apikeys/${apiKeyId}`);
  },

  async listDevices(): Promise<DeviceSummary[]> {
    const body = await apiClient.get<DeviceSummaryBody[]>("/auth/devices");
    return body.map((device) => ({
      id: device.id,
      deviceName: device.device_name,
      browser: device.browser,
      operatingSystem: device.operating_system,
      ipAddress: device.ip_address,
      location: device.location,
      lastLoginAt: device.last_login_at,
      isTrusted: device.is_trusted,
      trustedUntil: device.trusted_until,
    }));
  },

  async revokeDevice(deviceId: string): Promise<void> {
    await apiClient.delete(`/auth/devices/${deviceId}`);
  },

  async listSessions(): Promise<SessionSummary[]> {
    const body = await apiClient.get<SessionSummaryBody[]>("/auth/sessions");
    return body.map((session) => ({
      id: session.id,
      sessionId: session.session_id,
      ipAddress: session.ip_address,
      userAgent: session.user_agent,
      createdAt: session.created_at,
      lastActiveAt: session.last_active_at,
      expiresAt: session.expires_at,
    }));
  },

  async terminateSession(sessionDbId: string): Promise<void> {
    await apiClient.delete(`/auth/sessions/${sessionDbId}`);
  },

  async terminateAllSessions(): Promise<number> {
    const body = await apiClient.delete<{ terminated: number }>("/auth/sessions");
    return body.terminated;
  },
};
