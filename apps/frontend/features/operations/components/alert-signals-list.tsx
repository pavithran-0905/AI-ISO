"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { SEVERITY_RANK, SEVERITY_TONE } from "@/features/alerting/lib/severity";
import { RESOLVED_ALERT_STATUSES, type Alert } from "@/features/alerting/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { cn } from "@/utils/cn";

const MAX_VISIBLE = 8;

/**
 * Active-alert signals — the same real `GET /alerts` data and
 * "unresolved" interpretation (`RESOLVED_ALERT_STATUSES`) already
 * established by `features/dashboard/components/attention-required-section.tsx`
 * (§24 of that prompt: "do not duplicate alert-fetching logic"). The
 * one real difference from that section: clicking a signal here
 * *selects* it (for the context panel) rather than navigating away
 * immediately — a genuinely different interaction, not a second copy
 * of the fetch/derive logic.
 */
export function AlertSignalsList({
  organizationId,
  selectedAlertId,
  onSelect,
}: {
  organizationId: string;
  selectedAlertId: string | null;
  onSelect: (alert: Alert) => void;
}) {
  const query = useAlerts({ organizationId });

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-40 w-full">
      {query.data && <AlertList alerts={query.data} selectedAlertId={selectedAlertId} onSelect={onSelect} />}
    </SectionState>
  );
}

function AlertList({ alerts, selectedAlertId, onSelect }: { alerts: Alert[]; selectedAlertId: string | null; onSelect: (alert: Alert) => void }) {
  const active = alerts
    .filter((alert) => !RESOLVED_ALERT_STATUSES.has(alert.status))
    .sort((a, b) => {
      const severityDiff = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
      if (severityDiff !== 0) return severityDiff;
      return new Date(b.triggeredAt).getTime() - new Date(a.triggeredAt).getTime();
    });

  if (active.length === 0) {
    return <EmptyState title="No active alerts" description="Nothing currently needs attention." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {active.slice(0, MAX_VISIBLE).map((alert) => (
        <li key={alert.id}>
          <button type="button" onClick={() => onSelect(alert)} className="block w-full text-left">
            <Card className={cn("hover:border-muted-foreground/50 transition-colors", selectedAlertId === alert.id && "border-primary")}>
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
          </button>
        </li>
      ))}
      {active.length > MAX_VISIBLE && (
        <p className="text-muted-foreground text-center text-xs">+{active.length - MAX_VISIBLE} more requiring attention</p>
      )}
    </ul>
  );
}
