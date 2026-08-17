"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { setAuthTokenProvider, setUnauthorizedHandler } from "@/api/client";
import { authApi } from "@/auth/api";
import { getAccessToken, useAuthStore } from "@/auth/store";

/**
 * Wires the auth store into `@/api/client`'s injected provider hooks.
 * Mounted once, high in the tree (see `AppProviders`), so the client
 * never imports the store directly (avoiding a circular import: the
 * client is what `@/auth/api` itself calls through).
 */
export function AuthBootstrap({ children }: { children: React.ReactNode }): React.ReactNode {
  const clear = useAuthStore((state) => state.clear);

  useEffect(() => {
    setAuthTokenProvider(getAccessToken);
    setUnauthorizedHandler(clear);
  }, [clear]);

  return children;
}

const PROFILE_QUERY_KEY = ["auth", "profile"] as const;

/**
 * The session for the current tab: token-derived identity fields
 * (always available synchronously once authenticated) plus the fetched
 * profile (async, may still be loading). Prefer `role`/`organizationId`
 * from here over decoding a token yourself.
 */
export function useSession() {
  const status = useAuthStore((state) => state.status);
  const userId = useAuthStore((state) => state.userId);
  const role = useAuthStore((state) => state.role);
  const organizationId = useAuthStore((state) => state.organizationId);
  const isAuthenticated = status === "authenticated";

  const profileQuery = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: authApi.fetchProfile,
    enabled: isAuthenticated,
    staleTime: 5 * 60_000,
  });

  return {
    status,
    isAuthenticated,
    isLoading: status === "idle" || (isAuthenticated && profileQuery.isLoading),
    userId,
    role,
    organizationId,
    user: profileQuery.data ?? null,
  };
}
