/**
 * `services/notification-center-service/app/api/notifications.py` —
 * confirmed by direct source inspection. **`GET /notifications`,
 * `GET /notifications/{id}`, `POST /notifications/{id}/read`,
 * `POST /notifications/{id}/acknowledge`, and
 * `GET /notifications/{id}/deliveries` require no authentication at
 * all** — none declares a caller-identity dependency. `organization_id`
 * and `user_id` are both plain, caller-supplied query parameters,
 * never derived from or cross-checked against the JWT — this module
 * still always sends the real, currently-selected organization and
 * the real signed-in user's own id, the same discipline every other
 * tenant-isolation gap this session found, never a fix for the gap
 * itself. See `features/notifications/types/index.ts` and the
 * developer guide for the full finding.
 *
 * Deliberately not implemented here: `POST /notifications` (create),
 * `/send`, `/broadcast`, `DELETE /notifications/{id}`,
 * `POST /notifications/{id}/cancel` — all real, but authoring/admin
 * actions on someone else's outbound notification, not a recipient
 * viewing their own. Out of this feature's own scope (a Notification
 * Center, not a notification-authoring console) — see the developer
 * guide.
 */

import { apiClient } from "@/api/client";
import type { Notification, NotificationDelivery, NotificationSearchParams, NotificationSearchResult } from "@/features/notifications/types";

interface NotificationResponseBody {
  id: string;
  organization_id: string;
  user_id: string;
  category: string;
  priority: string;
  status: string;
  subject: string | null;
  body: string;
  template_id: string | null;
  source_service: string;
  source_event_type: string | null;
  correlation_id: string | null;
  expires_at: string | null;
  read_at: string | null;
  acknowledged_at: string | null;
  tags: string[];
  notification_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function toNotification(body: NotificationResponseBody): Notification {
  return {
    id: body.id,
    organizationId: body.organization_id,
    userId: body.user_id,
    category: body.category as Notification["category"],
    priority: body.priority as Notification["priority"],
    status: body.status as Notification["status"],
    subject: body.subject,
    body: body.body,
    templateId: body.template_id,
    sourceService: body.source_service,
    sourceEventType: body.source_event_type,
    correlationId: body.correlation_id,
    expiresAt: body.expires_at,
    readAt: body.read_at,
    acknowledgedAt: body.acknowledged_at,
    tags: body.tags,
    metadata: body.notification_metadata,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

interface DeliveryResponseBody {
  id: string;
  notification_id: string;
  channel: string;
  status: string;
  queued_at: string;
  sent_at: string | null;
  delivered_at: string | null;
  failed_at: string | null;
  attempts_used: number;
  provider_message_id: string | null;
  error: string | null;
  latency_ms: number | null;
}

function toDelivery(body: DeliveryResponseBody): NotificationDelivery {
  return {
    id: body.id,
    notificationId: body.notification_id,
    channel: body.channel as NotificationDelivery["channel"],
    status: body.status as NotificationDelivery["status"],
    queuedAt: body.queued_at,
    sentAt: body.sent_at,
    deliveredAt: body.delivered_at,
    failedAt: body.failed_at,
    attemptsUsed: body.attempts_used,
    providerMessageId: body.provider_message_id,
    error: body.error,
    latencyMs: body.latency_ms,
  };
}

const DEFAULT_LIMIT = 25;

export const notificationsApi = {
  async search(params: NotificationSearchParams): Promise<NotificationSearchResult> {
    const limit = params.limit ?? DEFAULT_LIMIT;
    const offset = params.offset ?? 0;
    const query = new URLSearchParams({ organization_id: params.organizationId, limit: String(limit), offset: String(offset) });
    if (params.userId) query.set("user_id", params.userId);
    if (params.status) query.set("status", params.status);
    if (params.category) query.set("category", params.category);
    if (params.sourceService) query.set("source_service", params.sourceService);
    const body = await apiClient.get<NotificationResponseBody[]>(`/notifications?${query.toString()}`);
    return { items: body.map(toNotification), offset, limit, hasMore: body.length === limit };
  },

  async get(organizationId: string, notificationId: string): Promise<Notification> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<NotificationResponseBody>(`/notifications/${notificationId}?${query.toString()}`);
    return toNotification(body);
  },

  async markRead(organizationId: string, notificationId: string): Promise<Notification> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.post<NotificationResponseBody>(`/notifications/${notificationId}/read?${query.toString()}`);
    return toNotification(body);
  },

  /** Real and distinct from "read" — `acknowledge()` also stamps
   * `read_at` server-side if it wasn't already set (confirmed:
   * `NotificationService.acknowledge`), so an acknowledged notification
   * is always shown as read too, never the reverse. */
  async acknowledge(organizationId: string, notificationId: string): Promise<Notification> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.post<NotificationResponseBody>(`/notifications/${notificationId}/acknowledge?${query.toString()}`);
    return toNotification(body);
  },

  async listDeliveries(organizationId: string, notificationId: string): Promise<NotificationDelivery[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<DeliveryResponseBody[]>(`/notifications/${notificationId}/deliveries?${query.toString()}`);
    return body.map(toDelivery);
  },
};
