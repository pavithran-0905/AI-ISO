/**
 * Types mirroring `services/notification-center-service`'s real
 * per-recipient `Notification` model, confirmed by direct source
 * inspection (`app/models/notification.py`, `app/schemas/notification.py`,
 * `app/api/notifications.py`). Distinct from two other real, unrelated
 * concepts this service also exposes: `NotificationAudit` (a separate
 * append-only action log, already consumed by
 * `features/audit` as the "notifications" audit source — never
 * conflated with this feature) and `NotificationAnnouncement` (a
 * pinned-bulletin-board content object, not built here — see the
 * developer guide).
 */

export const NOTIFICATION_CATEGORIES = [
  "alert", "warning", "information", "success", "failure", "critical", "reminder",
  "approval_request", "assignment", "system_announcement", "maintenance_notice", "digest", "custom",
] as const;
export type NotificationCategoryValue = (typeof NOTIFICATION_CATEGORIES)[number];

/** A notification's full real lifecycle — deliberately not collapsed
 * into a frontend-only "read/unread" enum (§9's own instruction: don't
 * claim a read-state change until backend confirmation, and this *is*
 * the backend's own state, not a derived one). */
export const NOTIFICATION_STATUSES = [
  "created", "queued", "sending", "sent", "delivered", "read", "acknowledged", "failed", "expired", "cancelled",
] as const;
export type NotificationStatusValue = (typeof NOTIFICATION_STATUSES)[number];

export const NOTIFICATION_PRIORITIES = ["critical", "high", "normal", "low", "background"] as const;
export type NotificationPriorityValue = (typeof NOTIFICATION_PRIORITIES)[number];

export const NOTIFICATION_CHANNELS = [
  "email", "sms", "slack", "teams", "discord", "webhook", "mobile_push", "browser_push", "in_app",
] as const;
export type NotificationChannelValue = (typeof NOTIFICATION_CHANNELS)[number];

/**
 * `NotificationResponse` (`GET /notifications`, `GET /notifications/{id}`).
 * `userId` is a plain string, not necessarily a UUID matching any other
 * service's identity space (same caveat as Prompt 015's audit
 * `actorId` — see this feature's own developer guide). `sourceService`/
 * `sourceEventType`/`correlationId` are free-text hints, not a
 * structured foreign key to another service's entity — confirmed
 * absent, so no deep-link is built from them (see `NotificationDeepLinkNote`
 * in the developer guide).
 */
export interface Notification {
  id: string;
  organizationId: string;
  userId: string;
  category: NotificationCategoryValue;
  priority: NotificationPriorityValue;
  status: NotificationStatusValue;
  subject: string | null;
  body: string;
  templateId: string | null;
  sourceService: string;
  sourceEventType: string | null;
  correlationId: string | null;
  expiresAt: string | null;
  readAt: string | null;
  acknowledgedAt: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

/**
 * Real filters confirmed on `GET /notifications`: `userId`, `status`
 * (exactly one `NotificationStatusValue`, never a set — there is no
 * dedicated "unread" filter value; unread means `readAt === null`,
 * which spans several statuses, so "Unread"/"Important" quick views
 * are applied client-side over the loaded page — see
 * `NotificationQuickView` in the developer guide), `category`,
 * `sourceService`. No free-text search parameter exists on this route.
 */
export interface NotificationSearchParams {
  organizationId: string;
  userId?: string;
  status?: NotificationStatusValue;
  category?: NotificationCategoryValue;
  sourceService?: string;
  limit?: number;
  offset?: number;
}

export interface NotificationSearchResult {
  items: Notification[];
  offset: number;
  limit: number;
  hasMore: boolean;
}

/** `DeliveryResponse` (`GET /notifications/{id}/deliveries`) — one
 * channel-dispatch attempt for one notification; a single notification
 * can have several (one per resolved channel). Distinct from a
 * notification's own `status`/`readAt` (whether the recipient has
 * seen it), which this type never duplicates. */
export interface NotificationDelivery {
  id: string;
  notificationId: string;
  channel: NotificationChannelValue;
  status: NotificationStatusValue;
  queuedAt: string;
  sentAt: string | null;
  deliveredAt: string | null;
  failedAt: string | null;
  attemptsUsed: number;
  providerMessageId: string | null;
  error: string | null;
  latencyMs: number | null;
}

/** The three real, in-page "quick views" over one already-fetched page
 * — never a separate fetch (see `NotificationSearchParams`'s own
 * docstring). "Unread"/"Important" are frontend-applied filters over
 * real fields (`readAt`, `priority`), not backend query parameters. */
export const NOTIFICATION_QUICK_VIEWS = ["all", "unread", "important"] as const;
export type NotificationQuickView = (typeof NOTIFICATION_QUICK_VIEWS)[number];
