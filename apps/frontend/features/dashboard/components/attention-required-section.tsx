"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge, type StatusTone } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlerts } from "@/features/dashboard/hooks/use-alerts";
import { ALERT_SEVERITIES, RESOLVED_ALERT_STATUSES, type Alert, type AlertSeverity } from "@/features/dashboard/types";
import { formatRelativeTime } from "@/lib/relative-time";

/** Alert severity is its own taxonomy, distinct from the operational
 * `StatusState` vocabulary (`@/lib/status`) — reuses the same 10-tone
 * palette rather than inventing new colors (docs/frontend Prompt 002
 * §18), just mapped for a different axis. */
const SEVERITY_TONE: Record<AlertSeverity, StatusTone> = {
  critical: "danger",
  high: "warning",
  medium: "warning",
  low: "info",
  info: "neutral",
};

const SEVERITY_RANK: Record<AlertSeverity, number> = Object.fromEntries(
  ALERT_SEVERITIES.map((severity, index) => [severity, index]),
) as Record<AlertSeverity, number>;

const MAX_VISIBLE = 5;

/**
 * Attention Required (§9, Level 3) — every currently-unresolved alert
 * from `GET /alerts`, sorted by severity then recency. "Unresolved" is
 * this dashboard's own interpretation (`RESOLVED_ALERT_STATUSES`), not
 * a backend-provided filter — the backend's `status` query param takes
 * exactly one value, so filtering the full set client-side avoids
 * issuing one request per status.
 */
export function AttentionRequiredSection({ organizationId }: { organizationId: string }) {
  const query = useAlerts(organizationId);

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
          <Card>
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
