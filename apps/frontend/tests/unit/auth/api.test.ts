import { afterEach, describe, expect, it, vi } from "vitest";

import { authApi } from "@/auth/api";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status,
      ok: status >= 200 && status < 300,
      json: () => Promise.resolve(body),
    }),
  );
}

const OK_ENVELOPE = (data: unknown) => ({
  success: true,
  message: "ok",
  data,
  meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
});

describe("authApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("login maps a TokenResponse body to AuthTokens", async () => {
    mockFetchOnce(
      200,
      OK_ENVELOPE({
        access_token: "at",
        refresh_token: "rt",
        token_type: "bearer",
        expires_in: 900,
      }),
    );

    const result = await authApi.login({ email: "a@b.com", password: "secret" });

    expect(result).toEqual({ accessToken: "at", refreshToken: "rt", tokenType: "bearer", expiresIn: 900 });
  });

  it("login maps an MfaChallengeResponse body to MfaChallenge", async () => {
    mockFetchOnce(200, OK_ENVELOPE({ mfa_required: true, mfa_challenge_id: "chal-1" }));

    const result = await authApi.login({ email: "a@b.com", password: "secret" });

    expect(result).toEqual({ mfaRequired: true, mfaChallengeId: "chal-1" });
  });

  it("login calls POST /auth/login without an auth header", async () => {
    mockFetchOnce(200, OK_ENVELOPE({ access_token: "at", refresh_token: "rt", token_type: "bearer", expires_in: 900 }));

    await authApi.login({ email: "a@b.com", password: "secret" });

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/auth/login");
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("refresh maps a TokenResponse body to AuthTokens", async () => {
    mockFetchOnce(200, OK_ENVELOPE({ access_token: "at2", refresh_token: "rt2", token_type: "bearer", expires_in: 900 }));

    const result = await authApi.refresh("rt");

    expect(result.accessToken).toBe("at2");
  });

  it("logout posts the refresh token", async () => {
    mockFetchOnce(200, OK_ENVELOPE({ success: true }));

    await authApi.logout("rt");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ refresh_token: "rt" });
  });

  it("fetchProfile maps snake_case fields to camelCase AuthUser", async () => {
    mockFetchOnce(
      200,
      OK_ENVELOPE({
        id: "user-1",
        email: "a@b.com",
        display_name: "A B",
        is_email_verified: true,
        mfa_enabled: false,
        last_login_at: null,
        created_at: "2026-01-01T00:00:00Z",
      }),
    );

    const result = await authApi.fetchProfile();

    expect(result).toEqual({
      id: "user-1",
      email: "a@b.com",
      displayName: "A B",
      isEmailVerified: true,
      mfaEnabled: false,
      lastLoginAt: null,
      createdAt: "2026-01-01T00:00:00Z",
    });
  });
});
