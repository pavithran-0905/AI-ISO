import { afterEach, describe, expect, it } from "vitest";

import { getAccessToken, getRefreshToken, useAuthStore } from "@/auth/store";

function makeToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

describe("useAuthStore", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
  });

  it("starts with no tokens, resolved to unauthenticated once rehydration runs", () => {
    // "idle" (the `create()` default) is only observable before
    // `persist`'s rehydration completes. In this test environment
    // `localStorage` access is synchronous, so by the time any test can
    // read the store, `onRehydrateStorage` has already run and — since
    // there's nothing in storage — resolved status to "unauthenticated".
    // A real browser has the same eventual state; only the timing differs.
    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.status).toBe("unauthenticated");
  });

  it("setTokens decodes the access token's claims into state", () => {
    const accessToken = makeToken({
      sub: "user-1",
      iss: "ai-ios",
      iat: 1,
      exp: 9_999_999_999,
      jti: "j1",
      role: "operator",
      organization_id: "org-1",
    });

    useAuthStore.getState().setTokens({
      accessToken,
      refreshToken: "refresh-1",
      tokenType: "bearer",
      expiresIn: 900,
    });

    const state = useAuthStore.getState();
    expect(state.status).toBe("authenticated");
    expect(state.userId).toBe("user-1");
    expect(state.role).toBe("operator");
    expect(state.organizationId).toBe("org-1");
  });

  it("setTokens tolerates the documented gap of a missing role/organization_id claim", () => {
    const accessToken = makeToken({ sub: "user-1", iss: "ai-ios", iat: 1, exp: 9_999_999_999, jti: "j1" });

    useAuthStore.getState().setTokens({
      accessToken,
      refreshToken: "refresh-1",
      tokenType: "bearer",
      expiresIn: 900,
    });

    const state = useAuthStore.getState();
    expect(state.status).toBe("authenticated");
    expect(state.role).toBeNull();
    expect(state.organizationId).toBeNull();
  });

  it("clear resets to unauthenticated with no tokens", () => {
    useAuthStore.getState().setTokens({
      accessToken: makeToken({ sub: "u", iss: "ai-ios", iat: 1, exp: 9_999_999_999, jti: "j" }),
      refreshToken: "r",
      tokenType: "bearer",
      expiresIn: 900,
    });

    useAuthStore.getState().clear();

    const state = useAuthStore.getState();
    expect(state.status).toBe("unauthenticated");
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
  });

  it("getAccessToken/getRefreshToken read the store without subscribing", () => {
    useAuthStore.getState().setTokens({
      accessToken: makeToken({ sub: "u", iss: "ai-ios", iat: 1, exp: 9_999_999_999, jti: "j" }),
      refreshToken: "refresh-xyz",
      tokenType: "bearer",
      expiresIn: 900,
    });

    expect(getAccessToken()).not.toBeNull();
    expect(getRefreshToken()).toBe("refresh-xyz");
  });
});
