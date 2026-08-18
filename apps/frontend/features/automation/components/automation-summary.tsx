"use client";

import { Alert } from "@/components/feedback/alert";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAutomationStatistics } from "@/features/automation/hooks/use-jobs";
import { formatDurationSeconds } from "@/features/automation/lib/duration";
import { formatRelativeTime } from "@/lib/relative-time";

/**
 * Real backend-computed aggregates from `GET /automation/statistics`
 * (§4: "use actual V1 data ... do not fabricate metrics").
 *
 * `successRate`/`failureRate` come back as 0–1 fractions and are
 * converted to a percentage for display — the one transformation
 * applied, and only because the underlying value is unambiguous.
 *
 * The staleness notice is not decoration: the backend computes this
 * snapshot once per organization and never recomputes it (no worker,
 * route, or scheduler calls `recompute`), so a figure here can be
 * arbitrarily old. Showing `computedAt` is the honest way to present
 * a number the platform will not refresh.
 */
export function AutomationSummary({ organizationId }: { organizationId: string }) {
  const query = useAutomationStatistics(organizationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data && (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard label="Automations" value={query.data.totalJobs} href="/automation/automations" />
            <MetricCard label="Executions" value={query.data.totalExecutions} href="/automation/executions" />
            <MetricCard label="Success rate" value={`${Math.round(query.data.successRate * 100)}%`} />
            <MetricCard label="Average runtime" value={formatDurationSeconds(query.data.averageRuntimeSeconds)} />
          </div>
          <Alert tone="info" title="These figures are a stored snapshot">
            Computed <time dateTime={query.data.computedAt}>{formatRelativeTime(query.data.computedAt)}</time>. AI-IOS
            does not recompute automation statistics automatically, so they may not reflect recent runs — the Executions
            list is always live.
          </Alert>
        </div>
      )}
    </SectionState>
  );
}
