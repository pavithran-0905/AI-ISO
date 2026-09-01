"use client";

import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { useReportingStatistics } from "@/features/reporting/hooks/use-reports";

/**
 * Reporting Status (§17) — `GET /reports/statistics`'s own real
 * execution counts. Deliberately not a report list/catalog (§17:
 * "avoid turning the dashboard into a report catalog") — just the four
 * counts the prompt itself names (recent/scheduled/failed/completed),
 * mapped onto this backend's own real field names.
 */
export function ReportingStatusWidget({ organizationId }: { organizationId: string }) {
  const query = useReportingStatistics(organizationId);

  return (
    <DashboardWidget
      title="Reporting"
      description="Report generation activity."
      action={{ label: "Open Reporting", href: "/reporting" }}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
    >
      {query.data && (
        <div className="grid grid-cols-2 gap-3">
          <MetricCard label="Reports" value={query.data.totalReports} />
          <MetricCard label="Scheduled runs" value={query.data.scheduledExecutions} />
          <MetricCard label="Successful runs" value={query.data.successfulExecutions} />
          <MetricCard label="Failed runs" value={query.data.failedExecutions} />
        </div>
      )}
    </DashboardWidget>
  );
}
