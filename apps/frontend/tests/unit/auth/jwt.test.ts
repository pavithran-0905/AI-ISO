import { describe, expect, it } from "vitest";

import { decodeTokenClaims, isTokenExpired } from "@/auth/jwt";

function makeToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

describe("decodeTokenClaims", () => {
  it("decodes a well-formed token's payload", () => {
    const token = makeToken({ sub: "user-1", iss: "ai-ios", iat: 1, exp: 2, jti: "abc" });

    expect(decodeTokenClaims(token)).toMatchObject({ sub: "user-1", iss: "ai-ios" });
  });

  it("decodes a token missing role/organization_id (the documented backend gap)", () => {
    const token = makeToken({ sub: "user-1", iss: "ai-ios", iat: 1, exp: 2, jti: "abc" });

    const claims = decodeTokenClaims(token);

    expect(claims?.role).toBeUndefined();
    expect(claims?.organization_id).toBeUndefined();
  });

  it("returns null for a malformed token", () => {
    expect(decodeTokenClaims("not-a-jwt")).toBeNull();
  });

  it("returns null for an unparsable payload segment", () => {
    expect(decodeTokenClaims("aGVhZGVy.bm90LWpzb24.sig")).toBeNull();
  });
});

describe("isTokenExpired", () => {
  it("is false when exp is in the future", () => {
    expect(isTokenExpired({ exp: 2000 } as never, 1000)).toBe(false);
  });

  it("is true when exp has passed", () => {
    expect(isTokenExpired({ exp: 500 } as never, 1000)).toBe(true);
  });

  it("is true when exp equals now", () => {
    expect(isTokenExpired({ exp: 1000 } as never, 1000)).toBe(true);
  });
});
