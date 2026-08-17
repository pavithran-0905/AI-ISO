"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { authApi } from "@/auth/api";
import { getRefreshToken, useAuthStore } from "@/auth/store";

/**
 * Logout (docs/frontend Prompt 004 §11): tells the backend to revoke
 * the refresh token (best-effort — a network failure here must not
 * block signing the user out locally, since staying "logged in" on a
 * device that can't reach the backend is worse than a token that
 * expires naturally), then clears frontend session state, the query
 * cache (§24 — no stale user-specific data survives into the next
 * session on a shared device), and redirects to `/login`. Clearing
 * `useAuthStore` before navigating (rather than relying on the route
 * change alone) is what prevents returning to a protected page through
 * stale client state, e.g. the back button.
 */
export function useLogout() {
  const clear = useAuthStore((state) => state.clear);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const logout = useCallback(async () => {
    setIsLoggingOut(true);
    try {
      await authApi.logout(getRefreshToken());
    } catch {
      // Best-effort: proceed with local sign-out regardless.
    } finally {
      clear("manual");
      queryClient.clear();
      setIsLoggingOut(false);
      router.push("/login");
    }
  }, [clear, queryClient, router]);

  return { logout, isLoggingOut };
}
