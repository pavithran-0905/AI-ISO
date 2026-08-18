"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { useAlertStatistics } from "@/features/alerting/hooks/use-alert-statistics";
import { formatDurationSeconds } from "@/features/alerting/lib/format-duration";
import { SEVERITY_LABEL, SEVERITY_TONE } from "@/features/alerting/lib/severity";
import { ALERT_SEVERITIES } from "@/features/alerting/types";

/**
 * Alerting Overview summary (§9, Level 1). Two data sources, kept
 * visually distinct on purpose:
 *  - Severity tiles: counted client-side from `GET /alerts`' full,
 *    unpaginated result for this org — honest because the endpoint has
 *    no pagination to hide anything behind (unlike a bounded scan over
 *    a paginated list, which would need to be labeled incomplete).
 *  - The four metric tiles below: real backend-computed values from
 *    `GET /alert-statistics`, never derived by the frontend.
 */
export function AlertSummary({ organizationId }: { organizationId: string }) {
  const alertsQuery = useAlerts({ organizationId });
  const statsQuery = useAlertStatistics(organizationId);

  return (
    <SectionState
      isLoading={alertsQuery.isLoading || statsQuery.isLoading}
      isError={alertsQuery.isError || statsQuery.isError}
      error={alertsQuery.error ?? statsQuery.error}
      onRetry={() => {
        alertsQuery.refetch();
        statsQuery.refetch();
      }}
    >
      {alertsQuery.data && statsQuery.data && (
        <div className="flex flex-col gap-4">
          {alertsQuery.data.length === 0 ? (
            <EmptyState title="No alerts yet" description="Nothing has been raised for this organization yet." />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {ALERT_SEVERITIES.map((severity) => {
                const count = alertsQuery.data.filter((alert) => alert.severity === severity).length;
                if (count === 0) return null;
                return (
                  <Card key={severity}>
                    <CardContent className="flex flex-col items-start gap-2 p-4">
                      <StatusBadge tone={SEVERITY_TONE[severity]} label={SEVERITY_LABEL[severity]} />
                      <p className="text-2xl font-semibold tabular-nums">{count}</p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard label="Total alerts" value={statsQuery.data.totalAlerts} />
            <MetricCard label="Open" value={statsQuery.data.openAlertCount} />
            <MetricCard label="Avg. time to acknowledge" value={formatDurationSeconds(statsQuery.data.mttaSeconds) ?? "—"} />
            <MetricCard label="Avg. time to resolve" value={formatDurationSeconds(statsQuery.data.mttrSeconds) ?? "—"} />
          </div>
        </div>
      )}
    </SectionState>
  );
}
