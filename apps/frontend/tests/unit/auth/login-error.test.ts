import { describe, expect, it } from "vitest";

import { ApiNetworkError, ApiRequestError, ApiTimeoutError } from "@/api/client";
import { getLoginErrorMessage } from "@/auth/login-error";

describe("getLoginErrorMessage", () => {
  it("gives the same generic message for 400 and 401, never revealing whether the email exists", () => {
    const message400 = getLoginErrorMessage(new ApiRequestError(400, "user not found", "X", []));
    const message401 = getLoginErrorMessage(new ApiRequestError(401, "invalid password", "X", []));
    expect(message400).toBe("Unable to sign in with those credentials.");
    expect(message400).toBe(message401);
  });

  it("does not leak the backend's own error message", () => {
    const message = getLoginErrorMessage(
      new ApiRequestError(500, "psycopg2.OperationalError: connection refused at db:5432", "X", []),
    );
    expect(message).not.toContain("psycopg2");
    expect(message).not.toContain("5432");
  });

  it.each([
    [403, "This account isn't allowed to sign in right now. Contact your administrator."],
    [429, "Too many sign-in attempts. Please wait a moment and try again."],
    [500, "Something went wrong on our end. Please try again."],
    [502, "Something went wrong on our end. Please try again."],
    [503, "Something went wrong on our end. Please try again."],
    [418, "Unable to sign in right now. Please try again."],
  ])("maps status %i to a safe message", (status, expected) => {
    expect(getLoginErrorMessage(new ApiRequestError(status, "internal detail", "X", []))).toBe(expected);
  });

  it("maps a network failure to the exact §19 wording", () => {
    expect(getLoginErrorMessage(new ApiNetworkError("/auth/login", new Error("offline")))).toBe(
      "Unable to connect to the authentication service. Please try again.",
    );
  });

  it("maps a timeout to a dedicated message", () => {
    expect(getLoginErrorMessage(new ApiTimeoutError("/auth/login"))).toBe(
      "The sign-in request timed out. Please try again.",
    );
  });

  it("falls back to a generic message for an unrecognized error shape", () => {
    expect(getLoginErrorMessage(new Error("something bizarre"))).toBe("Unable to sign in right now. Please try again.");
    expect(getLoginErrorMessage("not even an Error")).toBe("Unable to sign in right now. Please try again.");
  });
});
