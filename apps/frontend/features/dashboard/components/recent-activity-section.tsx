"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import { EXECUTION_STATUS_TO_STATUS } from "@/features/automation/lib/status-maps";
import type { AutomationExecution } from "@/features/automation/types";
import { formatRelativeTime } from "@/lib/relative-time";

const MAX_VISIBLE = 5;

/**
 * Recent Activity (§10, Level 4) — sourced from
 * `GET /automation/executions` (newest-first per the endpoint's own
 * docstring). Labeled specifically as automation activity, not generic
 * "platform activity": no cross-platform audit/activity feed exists in
 * Backend V1 (see `docs/frontend/backend-v1-integration-limitations.md`).
 *
 * Execution fetching now lives in `@/features/automation` (Prompt 009)
 * — this section is a consumer, not a second copy of the fetch logic
 * (§28: "do not duplicate automation API logic in Dashboard").
 */
export function RecentActivitySection({ organizationId }: { organizationId: string }) {
  const query = useExecutions({ organizationId });

  return (
    <SectionState
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-40 w-full"
    >
      {query.data && <ActivityList executions={query.data} />}
    </SectionState>
  );
}

function ActivityList({ executions }: { executions: AutomationExecution[] }) {
  if (executions.length === 0) {
    return <EmptyState title="No recent automation activity" description="Nothing has run yet for this organization." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {executions.slice(0, MAX_VISIBLE).map((execution) => {
        const timestamp = execution.completedAt ?? execution.startedAt ?? execution.createdAt;
        return (
          <li key={execution.id}>
            <Link href={`/automation/executions/${execution.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-sm font-medium">Run {execution.id.slice(0, 8)}</p>
                    <p className="text-muted-foreground text-xs">
                      <time dateTime={timestamp}>{formatRelativeTime(timestamp)}</time>
                    </p>
                  </div>
                  <StatusIndicator state={EXECUTION_STATUS_TO_STATUS[execution.status]} />
                </CardContent>
              </Card>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
