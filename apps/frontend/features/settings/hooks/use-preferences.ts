import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { preferencesApi } from "@/features/settings/api/preferences-api";
import type { PatchUserIdentityInput, UpdateUserPreferencesInput, UpdateUserProfileInput } from "@/features/settings/types";

export function useUserPreferences() {
  return useQuery({ queryKey: ["settings", "preferences"], queryFn: preferencesApi.getPreferences, staleTime: 60_000 });
}

export function useUpdateUserPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateUserPreferencesInput) => preferencesApi.updatePreferences(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "preferences"] }),
  });
}

export function useUserProfile() {
  return useQuery({ queryKey: ["settings", "profile"], queryFn: preferencesApi.getProfile, staleTime: 60_000 });
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateUserProfileInput) => preferencesApi.updateProfile(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "profile"] }),
  });
}

export function usePatchUserIdentity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, input }: { userId: string; input: PatchUserIdentityInput }) =>
      preferencesApi.patchIdentity(userId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "profile"] }),
  });
}
