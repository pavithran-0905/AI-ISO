"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlertAcknowledgements } from "@/features/alerting/hooks/use-alert-acknowledgements";
import { formatRelativeTime } from "@/lib/relative-time";

/**
 * `GET /alerts/{id}/acknowledgements` (§9) — a real, separate table;
 * potentially multiple rows per alert (one per acknowledge/resolve
 * action), so this is a list, not a single "acknowledged by" field.
 */
export function AlertAcknowledgementsList({ alertId }: { alertId: string }) {
  const query = useAlertAcknowledgements(alertId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No acknowledgements yet" description="No one has acknowledged or resolved this alert yet." />
        ) : (
          <ul className="flex flex-col gap-2">
            {[...query.data]
              .sort((a, b) => new Date(b.acknowledgedAt).getTime() - new Date(a.acknowledgedAt).getTime())
              .map((entry) => (
                <li key={entry.id}>
                  <Card>
                    <CardContent className="flex flex-col gap-0.5 p-3">
                      <p className="text-sm font-medium">
                        {entry.acknowledgedBy ?? "Unknown user"} · {entry.acknowledgementType}
                      </p>
                      <p className="text-muted-foreground text-xs">
                        <time dateTime={entry.acknowledgedAt}>{formatRelativeTime(entry.acknowledgedAt)}</time>
                      </p>
                      {entry.comment && <p className="text-sm">{entry.comment}</p>}
                      {entry.resolutionNotes && <p className="text-sm">{entry.resolutionNotes}</p>}
                    </CardContent>
                  </Card>
                </li>
              ))}
          </ul>
        ))}
    </SectionState>
  );
}
