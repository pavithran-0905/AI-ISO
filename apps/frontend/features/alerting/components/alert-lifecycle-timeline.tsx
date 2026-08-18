"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlertHistory } from "@/features/alerting/hooks/use-alert-history";
import { formatRelativeTime } from "@/lib/relative-time";

/**
 * `GET /alerts/{id}/history` (§9, Lifecycle) — a real per-alert audit
 * trail auto-populated on every status transition, not a fabricated
 * activity feed.
 */
export function AlertLifecycleTimeline({ alertId }: { alertId: string }) {
  const query = useAlertHistory(alertId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No history yet" description="No status transitions have been recorded for this alert." />
        ) : (
          <ul className="flex flex-col gap-2">
            {[...query.data]
              .sort((a, b) => new Date(b.changedAt).getTime() - new Date(a.changedAt).getTime())
              .map((entry) => (
                <li key={entry.id}>
                  <Card>
                    <CardContent className="flex flex-col gap-0.5 p-3">
                      <p className="text-sm font-medium">
                        {entry.fromStatus ? `${entry.fromStatus} → ${entry.toStatus}` : entry.toStatus}
                      </p>
                      <p className="text-muted-foreground text-xs">
                        {entry.changedBy ?? "System"} · <time dateTime={entry.changedAt}>{formatRelativeTime(entry.changedAt)}</time>
                        {entry.reason && ` · ${entry.reason}`}
                      </p>
                    </CardContent>
                  </Card>
                </li>
              ))}
          </ul>
        ))}
    </SectionState>
  );
}
