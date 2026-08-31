"use client";

import { Alert } from "@/components/feedback/alert";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { NotificationDeliveriesList } from "@/features/notifications/components/notification-deliveries-list";
import { useAcknowledgeNotification, useMarkNotificationRead } from "@/features/notifications/hooks/use-notifications";
import { categoryLabel, formatLabel, PRIORITY_TONES, STATUS_TONES } from "@/features/notifications/lib/format";
import type { Notification } from "@/features/notifications/types";
import { maskSensitiveEntries } from "@/lib/mask-sensitive";

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-sm">{value}</p>
    </div>
  );
}

/**
 * §8's Notification Detail. "Mark read"/"Acknowledge" are real,
 * separate mutations (§23: never conflated) — hidden once already in
 * that state, since both are confirmed idempotent server-side but
 * showing a control for a no-op invites confusion. No "related
 * resource" section: `Notification` has no structured entity
 * reference to another service's record (confirmed absent — see the
 * developer guide), so this never fabricates a deep link from the
 * free-text `sourceService`/`sourceEventType`/`correlationId` fields.
 */
export function NotificationDetailView({ organizationId, notification }: { organizationId: string; notification: Notification }) {
  const markRead = useMarkNotificationRead();
  const acknowledge = useAcknowledgeNotification();
  const maskedMetadata = Object.keys(notification.metadata).length > 0 ? maskSensitiveEntries(notification.metadata) : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={STATUS_TONES[notification.status]} label={formatLabel(notification.status)} />
        <StatusBadge tone={PRIORITY_TONES[notification.priority]} label={formatLabel(notification.priority)} />
        <StatusBadge tone="neutral" label={categoryLabel(notification.category)} />
      </div>

      <div className="flex flex-wrap gap-2">
        {notification.readAt === null && (
          <Button
            variant="outline"
            loading={markRead.isPending}
            onClick={() => markRead.mutate({ organizationId, notificationId: notification.id })}
          >
            Mark read
          </Button>
        )}
        {notification.status !== "acknowledged" && (
          <Button
            variant="outline"
            loading={acknowledge.isPending}
            onClick={() => acknowledge.mutate({ organizationId, notificationId: notification.id })}
          >
            Acknowledge
          </Button>
        )}
      </div>
      {(markRead.isError || acknowledge.isError) && (
        <Alert tone="danger" title="Action failed">
          {(markRead.error ?? acknowledge.error) instanceof Error ? (markRead.error ?? acknowledge.error)?.message : "Please try again."}
        </Alert>
      )}

      <div className="flex flex-col gap-4">
        <Field label="Message" value={notification.body} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Source service" value={notification.sourceService} />
          <Field label="Source event" value={notification.sourceEventType} />
          <Field label="Received" value={new Date(notification.createdAt).toLocaleString()} />
          <Field label="Read" value={notification.readAt ? new Date(notification.readAt).toLocaleString() : null} />
          <Field label="Acknowledged" value={notification.acknowledgedAt ? new Date(notification.acknowledgedAt).toLocaleString() : null} />
          <Field label="Expires" value={notification.expiresAt ? new Date(notification.expiresAt).toLocaleString() : null} />
        </div>
        {notification.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {notification.tags.map((tag) => (
              <StatusBadge key={tag} tone="neutral" label={tag} />
            ))}
          </div>
        )}
        {maskedMetadata && (
          <div className="flex flex-col gap-0.5">
            <p className="text-muted-foreground text-xs">Metadata</p>
            <pre className="bg-muted overflow-x-auto rounded-md p-2 font-mono text-xs">{JSON.stringify(maskedMetadata, null, 2)}</pre>
          </div>
        )}
      </div>

      <section>
        <p className="text-muted-foreground mb-2 text-xs">Deliveries</p>
        <NotificationDeliveriesList organizationId={organizationId} notificationId={notification.id} />
      </section>
    </div>
  );
}
