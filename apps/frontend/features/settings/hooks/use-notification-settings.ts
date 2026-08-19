import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { notificationsApi } from "@/features/settings/api/notifications-api";
import type { UpdateNotificationChannelInput, UpdateNotificationPreferencesInput } from "@/features/settings/types";

export function useNotificationPreferences(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "notifications", "preferences", organizationId],
    queryFn: () => notificationsApi.getPreferences(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useUpdateNotificationPreferences(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateNotificationPreferencesInput) => notificationsApi.updatePreferences(organizationId, input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["settings", "notifications", "preferences", organizationId] }),
  });
}

export function useNotificationChannels(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "notifications", "channels", organizationId],
    queryFn: () => notificationsApi.listChannels(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useSetNotificationChannel(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ channel, input }: { channel: string; input: UpdateNotificationChannelInput }) =>
      notificationsApi.setChannel(organizationId, channel, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "notifications", "channels", organizationId] }),
  });
}
