"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { authApi } from "@/auth/api";
import { useAuthStore } from "@/auth/store";
import type { LoginCredentials, LoginResult } from "@/auth/types";

/**
 * The login mutation (docs/frontend Prompt 004 §23's required flow:
 * `LoginForm → useLogin → auth API function → shared API client →
 * backend`). On a real token result, establishes the session and
 * clears the query cache so no previously-cached (or, on a shared
 * device, a different user's) data can leak into the new session
 * (§24). An MFA-challenge result is returned as-is, not treated as a
 * success — the login page decides how to present it.
 */
export function useLogin() {
  const setTokens = useAuthStore((state) => state.setTokens);
  const queryClient = useQueryClient();

  return useMutation<LoginResult, Error, LoginCredentials>({
    mutationFn: authApi.login,
    onSuccess: (result) => {
      if ("mfaRequired" in result) return;
      queryClient.clear();
      setTokens(result);
    },
  });
}
