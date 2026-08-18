"use client";

import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useReportingStatistics } from "@/features/reporting/hooks/use-reports";
import { formatDurationMs } from "@/features/reporting/lib/format-duration";

/** Real backend-computed aggregates from `GET /reports/statistics`
 * (§4: "do not fabricate metrics") — never derived by fetching and
 * counting reports client-side. */
export function ReportingSummary({ organizationId }: { organizationId: string }) {
  const query = useReportingStatistics(organizationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard label="Reports" value={query.data.totalReports} href="/reporting/reports" />
          <MetricCard
            label="Generations"
            value={query.data.totalExecutions}
            description={`${query.data.failedExecutions} failed`}
            href="/reporting/history"
          />
          <MetricCard label="Scheduled" value={query.data.scheduledExecutions} href="/reporting/schedules" />
          <MetricCard label="Avg. generation time" value={formatDurationMs(query.data.averageDurationMs) ?? "—"} />
        </div>
      )}
    </SectionState>
  );
}
