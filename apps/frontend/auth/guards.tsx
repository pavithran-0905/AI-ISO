"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSession } from "@/auth/session";
import { useAuthStore } from "@/auth/store";

export { isSafeReturnPath } from "@/auth/return-path";

const UNAUTHENTICATED_REDIRECT_PATH = "/login";
const DEFAULT_AUTHENTICATED_PATH = "/";

/**
 * Route-level protection (docs/frontend Prompt 001 §15, wired into
 * `app/(app)/layout.tsx` by Prompt 004 §10). This is a UX convenience
 * only — it redirects an unauthenticated browser tab away from a page
 * it can't usefully render. It is NOT a security boundary: every
 * protected backend call still requires (and independently verifies) a
 * bearer token server-side. See docs/frontend/architecture/authorization.md.
 */
export function AuthGuard({ children }: { children: React.ReactNode }): React.ReactNode {
  const router = useRouter();
  const pathname = usePathname();
  const { status, isAuthenticated } = useSession();
  const lastClearReason = useAuthStore((state) => state.lastClearReason);

  useEffect(() => {
    if (status !== "unauthenticated") return;
    const params = new URLSearchParams();
    // "return-to destination" — the login page reads this to send the
    // user back where they were headed instead of always landing on
    // the default authenticated page.
    if (pathname && pathname !== "/") params.set("from", pathname);
    // Only set when the store's own last `clear()` call was triggered
    // by a 401 (see `auth/session.tsx`) — never guessed at for a
    // visitor who was simply never signed in.
    if (lastClearReason === "expired") params.set("reason", "expired");
    const query = params.toString();
    router.replace(query ? `${UNAUTHENTICATED_REDIRECT_PATH}?${query}` : UNAUTHENTICATED_REDIRECT_PATH);
  }, [status, pathname, lastClearReason, router]);

  if (!isAuthenticated) return null;
  return children;
}

/**
 * The inverse of `AuthGuard` — keeps an already-authenticated user off
 * guest-only pages (login). Session restoration (Prompt 004 §21): if a
 * valid session already exists and the user opens `/login`, redirect
 * away instead of showing the form again.
 */
export function GuestGuard({
  children,
  redirectTo = DEFAULT_AUTHENTICATED_PATH,
}: {
  children: React.ReactNode;
  /** Where to send an already-authenticated visitor — defaults to the
   * canonical landing page, but the login page passes a validated
   * `?from=` here so returning from an expired session lands back
   * where the user was, not always the dashboard. */
  redirectTo?: string;
}): React.ReactNode {
  const router = useRouter();
  const { isAuthenticated } = useSession();

  useEffect(() => {
    if (isAuthenticated) router.replace(redirectTo);
  }, [isAuthenticated, redirectTo, router]);

  if (isAuthenticated) return null;
  return children;
}
