"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { SEVERITY_RANK, SEVERITY_TONE } from "@/features/alerting/lib/severity";
import { RESOLVED_ALERT_STATUSES, type Alert } from "@/features/alerting/types";
import { formatRelativeTime } from "@/lib/relative-time";

const MAX_VISIBLE = 5;

/**
 * Attention Required (§9, Level 3) — every currently-unresolved alert
 * from `GET /alerts`, sorted by severity then recency. "Unresolved" is
 * this dashboard's own interpretation (`RESOLVED_ALERT_STATUSES`), not
 * a backend-provided filter — the backend's `status` query param takes
 * exactly one value, so filtering the full set client-side avoids
 * issuing one request per status. Alert fetching now lives in
 * `@/features/alerting` (Prompt 007) — this section is a consumer, not
 * a second copy of the fetch logic (§24: "do not duplicate
 * alert-fetching logic inside Dashboard").
 */
export function AttentionRequiredSection({ organizationId }: { organizationId: string }) {
  const query = useAlerts({ organizationId });

  return (
    <SectionState
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-40 w-full"
    >
      {query.data && <AttentionList alerts={query.data} />}
    </SectionState>
  );
}

function AttentionList({ alerts }: { alerts: Alert[] }) {
  const unresolved = alerts
    .filter((alert) => !RESOLVED_ALERT_STATUSES.has(alert.status))
    .sort((a, b) => {
      const severityDiff = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
      if (severityDiff !== 0) return severityDiff;
      return new Date(b.triggeredAt).getTime() - new Date(a.triggeredAt).getTime();
    });

  if (unresolved.length === 0) {
    return <EmptyState title="No active alerts" description="Nothing currently needs attention." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {unresolved.slice(0, MAX_VISIBLE).map((alert) => (
        <li key={alert.id}>
          <Link href={`/alerting/alerts/${alert.id}`} className="block">
            <Card className="hover:border-muted-foreground/50 transition-colors">
              <CardContent className="flex items-start justify-between gap-3 p-3">
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-medium">{alert.title}</p>
                  <p className="text-muted-foreground text-xs">
                    {alert.source} · <time dateTime={alert.triggeredAt}>{formatRelativeTime(alert.triggeredAt)}</time>
                  </p>
                </div>
                <StatusBadge tone={SEVERITY_TONE[alert.severity]} label={alert.severity} className="shrink-0 uppercase" />
              </CardContent>
            </Card>
          </Link>
        </li>
      ))}
      {unresolved.length > MAX_VISIBLE && (
        <p className="text-muted-foreground text-center text-xs">
          +{unresolved.length - MAX_VISIBLE} more requiring attention
        </p>
      )}
    </ul>
  );
}
