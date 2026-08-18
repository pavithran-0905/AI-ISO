"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useFavoriteReports } from "@/features/reporting/hooks/use-reports";

/** `GET /reports/favorites/mine` (§4 "favourite/recent reports") — the
 * current user's own real, persisted favorites, not a client-side
 * "recently viewed" heuristic. */
export function FavoriteReportsList({ organizationId }: { organizationId: string }) {
  const query = useFavoriteReports(organizationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No favorite reports" description="Star a report from its detail page to pin it here." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((report) => (
              <li key={report.id}>
                <Link href={`/reporting/reports/${report.id}`} className="block">
                  <Card className="hover:border-muted-foreground/50 transition-colors">
                    <CardContent className="flex flex-col gap-0.5 p-3">
                      <p className="text-sm font-medium">{report.name}</p>
                      <p className="text-muted-foreground text-xs">
                        {report.category} · {report.reportType}
                      </p>
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
