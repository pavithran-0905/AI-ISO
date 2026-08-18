"use client";

import { FileBarChart } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { CitationsList } from "@/features/ai-assistant/components/citations-list";
import { useAiReports } from "@/features/ai-assistant/hooks/use-insights";
import { formatRelativeTime } from "@/lib/relative-time";

/** Every field is returned in full by the list endpoint — there is no
 * `GET /ai/reports/{id}`, so this shows the complete body and
 * citations inline per item rather than linking to a detail page that
 * doesn't exist. `generatedAt` is the one real timestamp anywhere in
 * this feature's list responses, so this is the one list genuinely
 * sortable by recency. */
export function AiReportList({ organizationId }: { organizationId: string }) {
  const reportsQuery = useAiReports(organizationId);
  const [sortNewestFirst, setSortNewestFirst] = useState(true);

  const sorted = useMemo(() => {
    if (!reportsQuery.data) return [];
    const items = [...reportsQuery.data];
    items.sort((a, b) => {
      const diff = new Date(a.generatedAt).getTime() - new Date(b.generatedAt).getTime();
      return sortNewestFirst ? -diff : diff;
    });
    return items;
  }, [reportsQuery.data, sortNewestFirst]);

  if (reportsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading AI reports">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (reportsQuery.isError) {
    return <p className="text-danger text-sm">Reports could not be loaded.</p>;
  }

  if (sorted.length === 0) {
    return <EmptyState icon={FileBarChart} title="No AI reports yet" description="Generate one above." />;
  }

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        onClick={() => setSortNewestFirst((value) => !value)}
        className="text-muted-foreground hover:text-foreground w-fit text-xs underline-offset-2 hover:underline"
      >
        Sort: {sortNewestFirst ? "Newest first" : "Oldest first"}
      </button>

      <ul className="flex flex-col gap-3">
        {sorted.map((report) => (
          <li key={report.id} className="border-border flex flex-col gap-2 rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-col gap-0.5">
                <span className="font-medium">{report.title}</span>
                <span className="text-muted-foreground text-xs">
                  <time dateTime={report.generatedAt}>{formatRelativeTime(report.generatedAt)}</time>
                </span>
              </div>
              <Badge variant="outline">{report.reportType}</Badge>
            </div>
            <p className="text-sm whitespace-pre-wrap">{report.body}</p>
            <CitationsList citations={report.citations} />
          </li>
        ))}
      </ul>
    </div>
  );
}
