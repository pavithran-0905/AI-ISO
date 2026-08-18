"use client";

import { EmptyState } from "@/components/feedback/empty-state";
import { Card, CardContent } from "@/components/data-display/card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useReportHistory } from "@/features/reporting/hooks/use-reports";
import { formatRelativeTime } from "@/lib/relative-time";

/** `GET /reports/history?report_id=...` (§14) — this report's own real
 * activity feed. */
export function ReportHistorySection({ organizationId, reportId }: { organizationId: string; reportId: string }) {
  const query = useReportHistory(organizationId, { reportId, limit: 50 });

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No history yet" description="Nothing has happened to this report yet." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((entry) => (
              <li key={entry.id}>
                <Card>
                  <CardContent className="flex items-start justify-between gap-3 p-3">
                    <div className="flex flex-col gap-0.5">
                      <p className="text-sm font-medium">{entry.summary}</p>
                      <p className="text-muted-foreground text-xs">{entry.event}</p>
                    </div>
                    <time dateTime={entry.occurredAt} className="text-muted-foreground shrink-0 text-xs">
                      {formatRelativeTime(entry.occurredAt)}
                    </time>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
