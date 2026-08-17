"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSession } from "@/auth/session";

/** No `/login` page exists yet (see the module docstring below), so an
 * unauthenticated redirect lands on the 401 destination instead of a
 * route that would itself 404. Point this at `/login` once that page
 * ships. */
const UNAUTHENTICATED_REDIRECT_PATH = "/unauthorized";
const DEFAULT_AUTHENTICATED_PATH = "/";

/**
 * Route-level protection (docs/frontend Prompt 001 §15). This is a UX
 * convenience only — it redirects an unauthenticated browser tab away
 * from a page it can't usefully render. It is NOT a security boundary:
 * every protected backend call still requires (and independently
 * verifies) a bearer token server-side. See
 * docs/frontend/architecture/authorization.md.
 *
 * Not yet wired into any route group — see the comment in
 * `app/(app)/layout.tsx` for why.
 */
export function AuthGuard({ children }: { children: React.ReactNode }): React.ReactNode {
  const router = useRouter();
  const pathname = usePathname();
  const { status, isAuthenticated } = useSession();

  useEffect(() => {
    if (status !== "unauthenticated") return;
    // §27 "return-to destination": once a real login flow exists, it
    // reads this to send the user back where they were headed rather
    // than always landing on the dashboard.
    const from = pathname && pathname !== "/" ? `?from=${encodeURIComponent(pathname)}` : "";
    router.replace(`${UNAUTHENTICATED_REDIRECT_PATH}${from}`);
  }, [status, pathname, router]);

  if (!isAuthenticated) return null;
  return children;
}

/** The inverse of `AuthGuard` — keeps an already-authenticated user off
 * public-only pages (login, register). */
export function GuestGuard({ children }: { children: React.ReactNode }): React.ReactNode {
  const router = useRouter();
  const { isAuthenticated } = useSession();

  useEffect(() => {
    if (isAuthenticated) router.replace(DEFAULT_AUTHENTICATED_PATH);
  }, [isAuthenticated, router]);

  if (isAuthenticated) return null;
  return children;
}
