"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlertCorrelations } from "@/features/alerting/hooks/use-alert-correlations";
import { formatRelativeTime } from "@/lib/relative-time";

/**
 * `GET /alerts/{id}/correlations` (§9) — only alerts correlated *to*
 * this one as children; there's no `group_id` or standalone grouping
 * endpoint, so this can't show a full correlation cluster, only this
 * alert's own children. See
 * `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function AlertCorrelationsList({ alertId }: { alertId: string }) {
  const query = useAlertCorrelations(alertId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No correlated alerts" description="No other alerts have been correlated to this one." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((entry) => (
              <li key={entry.id}>
                <Link href={`/alerting/alerts/${entry.childAlertId}`} className="block">
                  <Card className="hover:border-muted-foreground/50 transition-colors">
                    <CardContent className="flex flex-col gap-0.5 p-3">
                      <p className="text-sm font-medium">{entry.correlationType}</p>
                      <p className="text-muted-foreground text-xs">
                        <time dateTime={entry.correlatedAt}>{formatRelativeTime(entry.correlatedAt)}</time>
                      </p>
                    </CardContent>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
