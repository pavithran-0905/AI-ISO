import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { notificationsApi } from "@/features/notifications/api/notifications-api";
import type { NotificationSearchParams } from "@/features/notifications/types";

const LIST_KEY = "notifications";

export function useNotifications(params: NotificationSearchParams | null) {
  return useQuery({
    queryKey: [LIST_KEY, "list", params],
    queryFn: () => notificationsApi.search(params as NotificationSearchParams),
    enabled: params !== null,
    staleTime: 15_000,
  });
}

/** The bell/popover's own data source — a small, bounded, most-recent
 * page for the signed-in user. No unread-count route exists
 * (`NotificationRepository.count_unread` is real but never called from
 * any route, confirmed by source inspection) and §10 explicitly
 * forbids computing a total from a paginated client dataset, so this
 * never renders a number — only whether *any* item in this bounded
 * page is unread (`readAt === null`), reused directly for the popover
 * body itself rather than a second call. A light 60s poll (real,
 * working `refetchInterval` — not a fabricated push channel; none
 * exists, confirmed absent) keeps it reasonably current without
 * hammering an unauthenticated, unscoped-by-JWT route continuously. */
export function useRecentNotifications(organizationId: string | null, userId: string | null) {
  return useQuery({
    queryKey: [LIST_KEY, "recent", organizationId, userId],
    queryFn: () => notificationsApi.search({ organizationId: organizationId as string, userId: userId as string, limit: 8, offset: 0 }),
    enabled: organizationId !== null && userId !== null,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useNotification(organizationId: string | null, notificationId: string | null) {
  return useQuery({
    queryKey: [LIST_KEY, "detail", organizationId, notificationId],
    queryFn: () => notificationsApi.get(organizationId as string, notificationId as string),
    enabled: organizationId !== null && notificationId !== null,
    staleTime: 15_000,
  });
}

export function useNotificationDeliveries(organizationId: string | null, notificationId: string | null) {
  return useQuery({
    queryKey: [LIST_KEY, "deliveries", organizationId, notificationId],
    queryFn: () => notificationsApi.listDeliveries(organizationId as string, notificationId as string),
    enabled: organizationId !== null && notificationId !== null,
    staleTime: 15_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ organizationId, notificationId }: { organizationId: string; notificationId: string }) =>
      notificationsApi.markRead(organizationId, notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LIST_KEY] });
    },
  });
}

export function useAcknowledgeNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ organizationId, notificationId }: { organizationId: string; notificationId: string }) =>
      notificationsApi.acknowledge(organizationId, notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LIST_KEY] });
    },
  });
}
