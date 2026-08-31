"use client";

import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { formatLabel, STATUS_TONES } from "@/features/notifications/lib/format";
import { useNotificationDeliveries } from "@/features/notifications/hooks/use-notifications";

/** `GET /notifications/{id}/deliveries` (§8's "related resource"-
 * adjacent detail) — one row per channel this notification was
 * resolved to and dispatched over, a genuinely separate concept from
 * the notification's own read/unread state (see the type's own
 * docstring). */
export function NotificationDeliveriesList({ organizationId, notificationId }: { organizationId: string; notificationId: string }) {
  const query = useNotificationDeliveries(organizationId, notificationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-24 w-full">
      {query.data &&
        (query.data.length === 0 ? (
          <p className="text-muted-foreground text-sm">No delivery attempts recorded for this notification.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((delivery) => (
              <li key={delivery.id} className="border-border flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{formatLabel(delivery.channel)}</span>
                  <StatusBadge tone={STATUS_TONES[delivery.status]} label={formatLabel(delivery.status)} />
                </div>
                <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
                  {delivery.attemptsUsed > 0 && <span>{delivery.attemptsUsed} attempt(s)</span>}
                  {delivery.latencyMs !== null && <span>{Math.round(delivery.latencyMs)}ms</span>}
                  {delivery.error && <span className="text-danger">{delivery.error}</span>}
                </div>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
