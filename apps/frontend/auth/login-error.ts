import { ApiNetworkError, ApiRequestError, ApiTimeoutError } from "@/api/client";

/**
 * Maps a login failure to a safe, user-facing message (docs/frontend
 * Prompt 004 §7/§19) — never the raw backend message, which could
 * reveal whether an email exists, expose internals, or otherwise leak
 * more than "sign-in didn't work." Every branch here is deliberately
 * generic for that reason, not an oversight.
 */
export function getLoginErrorMessage(error: unknown): string {
  if (error instanceof ApiNetworkError) {
    return "Unable to connect to the authentication service. Please try again.";
  }
  if (error instanceof ApiTimeoutError) {
    return "The sign-in request timed out. Please try again.";
  }
  if (error instanceof ApiRequestError) {
    switch (error.status) {
      case 400:
      case 401:
        // Deliberately identical for both — §7: "do not unnecessarily
        // reveal whether a username exists."
        return "Unable to sign in with those credentials.";
      case 403:
        return "This account isn't allowed to sign in right now. Contact your administrator.";
      case 429:
        return "Too many sign-in attempts. Please wait a moment and try again.";
      case 500:
      case 502:
      case 503:
        return "Something went wrong on our end. Please try again.";
      default:
        return "Unable to sign in right now. Please try again.";
    }
  }
  return "Unable to sign in right now. Please try again.";
}
