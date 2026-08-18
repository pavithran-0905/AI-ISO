"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlertNotifications } from "@/features/alerting/hooks/use-alert-notifications";
import { formatRelativeTime } from "@/lib/relative-time";

const NOTIFICATION_STATUS_TONE: Record<string, "success" | "danger" | "pending" | "neutral"> = {
  sent: "success",
  delivered: "success",
  failed: "danger",
  pending: "pending",
};

/** `GET /alerts/{id}/notifications` (§9) — the real delivery attempts
 * for this alert's routed channels, including retry count and any
 * delivery error. */
export function AlertNotificationsList({ alertId }: { alertId: string }) {
  const query = useAlertNotifications(alertId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No notifications sent" description="No delivery attempts have been recorded for this alert." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((entry) => (
              <li key={entry.id}>
                <Card>
                  <CardContent className="flex items-start justify-between gap-3 p-3">
                    <div className="flex flex-col gap-0.5">
                      <p className="text-sm font-medium">{entry.channel}</p>
                      <p className="text-muted-foreground text-xs">
                        {entry.retryCount > 0 && `${entry.retryCount} retr${entry.retryCount === 1 ? "y" : "ies"} · `}
                        {entry.sentAt ? (
                          <time dateTime={entry.sentAt}>{formatRelativeTime(entry.sentAt)}</time>
                        ) : (
                          "Not yet sent"
                        )}
                      </p>
                      {entry.errorMessage && <p className="text-danger text-xs">{entry.errorMessage}</p>}
                    </div>
                    <StatusBadge tone={NOTIFICATION_STATUS_TONE[entry.status] ?? "neutral"} label={entry.status} className="shrink-0" />
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
