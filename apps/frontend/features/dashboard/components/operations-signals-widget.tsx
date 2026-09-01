"use client";

import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { RESOLVED_ALERT_STATUSES } from "@/features/alerting/types";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import type { ExecutionStatusValue } from "@/features/automation/types";
import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";
import { MetricCard } from "@/features/dashboard/components/metric-card";

/** The same interpretation `features/operations/components/
 * automation-signals-list.tsx` (Prompt 019) already established for
 * "needs attention" runs — kept identical rather than a second,
 * possibly-drifting definition. */
const PROBLEM_STATUSES: ReadonlySet<ExecutionStatusValue> = new Set(["failed", "timed_out"]);

/**
 * Operations Signals (§14) — a navigational bridge into Operations
 * Workspace (Prompt 019), never a second copy of its correlation logic
 * (§14: "do not duplicate correlation logic" — alert-to-alert
 * correlation and execution target-ids stay exclusively inside that
 * workspace). Reuses the exact same `useAlerts({organizationId})` and
 * `useExecutions({organizationId})` queries `AttentionRequiredSection`
 * and `RecentActivitySection` already fetch on this same page — React
 * Query dedupes identical `queryKey`s (§36), so this widget issues zero
 * additional requests when those core sections are also visible; it
 * only re-derives two counts from data already in the cache.
 */
export function OperationsSignalsWidget({ organizationId }: { organizationId: string }) {
  const alertsQuery = useAlerts({ organizationId });
  const executionsQuery = useExecutions({ organizationId });

  const isLoading = alertsQuery.isLoading || executionsQuery.isLoading;
  const isError = alertsQuery.isError || executionsQuery.isError;

  const unresolvedAlerts = alertsQuery.data?.filter((alert) => !RESOLVED_ALERT_STATUSES.has(alert.status)).length ?? 0;
  const failedRuns = executionsQuery.data?.filter((execution) => PROBLEM_STATUSES.has(execution.status)).length ?? 0;

  return (
    <DashboardWidget
      title="Operations Workspace"
      description="Investigate active alerts and automation activity together."
      action={{ label: "Open Operations Workspace", href: "/operations" }}
      isLoading={isLoading}
      isError={isError}
      error={alertsQuery.error ?? executionsQuery.error}
      onRetry={() => {
        alertsQuery.refetch();
        executionsQuery.refetch();
      }}
      skeletonClassName="h-16 w-full"
    >
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Unresolved alerts" value={unresolvedAlerts} />
        <MetricCard label="Failed automation runs" value={failedRuns} />
      </div>
    </DashboardWidget>
  );
}
