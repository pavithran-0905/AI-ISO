"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAutomationExecutions } from "@/features/dashboard/hooks/use-automation-executions";
import type { AutomationExecution, ExecutionStatusValue } from "@/features/dashboard/types";
import { formatRelativeTime } from "@/lib/relative-time";
import type { StatusState } from "@/lib/status";

/** `ExecutionStatus` (backend) → the canonical status taxonomy. */
const EXECUTION_STATUS_TO_STATUS: Record<ExecutionStatusValue, StatusState> = {
  pending: "pending",
  running: "running",
  paused: "stopped",
  completed: "completed",
  failed: "failed",
  cancelled: "cancelled",
  timed_out: "failed",
  rolled_back: "cancelled",
};

const MAX_VISIBLE = 5;

/**
 * Recent Activity (§10, Level 4) — sourced from
 * `GET /automation/executions` (newest-first per the endpoint's own
 * docstring). Labeled specifically as automation activity, not generic
 * "platform activity": no cross-platform audit/activity feed exists in
 * Backend V1 (see `docs/frontend/backend-v1-integration-limitations.md`).
 */
export function RecentActivitySection({ organizationId }: { organizationId: string }) {
  const query = useAutomationExecutions(organizationId);

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
        const timestamp = execution.completedAt ?? execution.startedAt;
        return (
          <li key={execution.id}>
            <Card>
              <CardContent className="flex items-center justify-between gap-3 p-3">
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-medium">Job {execution.jobId}</p>
                  {timestamp && (
                    <p className="text-muted-foreground text-xs">
                      <time dateTime={timestamp}>{formatRelativeTime(timestamp)}</time>
                    </p>
                  )}
                </div>
                <StatusIndicator state={EXECUTION_STATUS_TO_STATUS[execution.status]} />
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
