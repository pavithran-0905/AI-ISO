import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { securityApi } from "@/features/settings/api/security-api";
import type { CreateApiKeyInput } from "@/features/settings/types";

export function useEnableMfa() {
  return useMutation({ mutationFn: securityApi.enableMfa });
}

export function useVerifyMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => securityApi.verifyMfa(code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "profile"] }),
  });
}

export function useDisableMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => securityApi.disableMfa(code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "profile"] }),
  });
}

export function useRequestPasswordReset() {
  return useMutation({ mutationFn: (email: string) => securityApi.requestPasswordReset(email) });
}

export function useApiKeys() {
  return useQuery({ queryKey: ["settings", "security", "apikeys"], queryFn: securityApi.listApiKeys, staleTime: 30_000 });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateApiKeyInput) => securityApi.createApiKey(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "security", "apikeys"] }),
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (apiKeyId: string) => securityApi.revokeApiKey(apiKeyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "security", "apikeys"] }),
  });
}

export function useDevices() {
  return useQuery({ queryKey: ["settings", "security", "devices"], queryFn: securityApi.listDevices, staleTime: 30_000 });
}

export function useRevokeDevice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (deviceId: string) => securityApi.revokeDevice(deviceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "security", "devices"] }),
  });
}

export function useSessions() {
  return useQuery({ queryKey: ["settings", "security", "sessions"], queryFn: securityApi.listSessions, staleTime: 30_000 });
}

export function useTerminateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionDbId: string) => securityApi.terminateSession(sessionDbId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "security", "sessions"] }),
  });
}

export function useTerminateAllSessions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: securityApi.terminateAllSessions,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "security", "sessions"] }),
  });
}
