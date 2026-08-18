"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useReportHistory } from "@/features/reporting/hooks/use-reports";
import { formatRelativeTime } from "@/lib/relative-time";

/** `GET /reports/history` (§4 "recent generations") — the real
 * user-visible activity feed, distinct from the write-only security
 * audit trail (`ReportAudit`), which has no GET endpoint at all. */
export function RecentGenerationsList({ organizationId, limit = 5 }: { organizationId: string; limit?: number }) {
  const query = useReportHistory(organizationId, { limit });

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No recent activity" description="Nothing has been generated for this organization yet." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((entry) => (
              <li key={entry.id}>
                <Link href={`/reporting/reports/${entry.jobId}`} className="block">
                  <Card className="hover:border-muted-foreground/50 transition-colors">
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
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
