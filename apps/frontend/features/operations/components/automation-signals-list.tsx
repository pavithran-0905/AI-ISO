"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import { EXECUTION_STATUS_TO_STATUS } from "@/features/automation/lib/status-maps";
import type { AutomationExecution } from "@/features/automation/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { cn } from "@/utils/cn";

const MAX_VISIBLE = 8;
/** This workspace's own interpretation of "recent failure" — not a
 * backend-provided filter (`GET /automation/executions` supports one
 * `status` value, not a set; the real terminal-bad values are
 * `failed`/`timed_out`, confirmed in `features/automation/types`). */
const PROBLEM_STATUSES = new Set(["failed", "timed_out"]);

/**
 * Automation-execution signals — the same real `GET /automation/executions`
 * data `features/dashboard/components/recent-activity-section.tsx`
 * already fetches (newest-first, per that endpoint's own docstring).
 * Failures are surfaced first, then the rest — clicking selects a
 * signal for the context panel rather than navigating away.
 */
export function AutomationSignalsList({
  organizationId,
  selectedExecutionId,
  onSelect,
}: {
  organizationId: string;
  selectedExecutionId: string | null;
  onSelect: (execution: AutomationExecution) => void;
}) {
  const query = useExecutions({ organizationId });

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-40 w-full">
      {query.data && <ExecutionList executions={query.data} selectedExecutionId={selectedExecutionId} onSelect={onSelect} />}
    </SectionState>
  );
}

function ExecutionList({
  executions,
  selectedExecutionId,
  onSelect,
}: {
  executions: AutomationExecution[];
  selectedExecutionId: string | null;
  onSelect: (execution: AutomationExecution) => void;
}) {
  if (executions.length === 0) {
    return <EmptyState title="No recent automation activity" description="Nothing has run yet for this organization." />;
  }

  const ordered = [...executions].sort((a, b) => {
    const problemDiff = Number(PROBLEM_STATUSES.has(b.status)) - Number(PROBLEM_STATUSES.has(a.status));
    if (problemDiff !== 0) return problemDiff;
    return 0; // already newest-first from the backend; keep that order within each tier
  });

  return (
    <ul className="flex flex-col gap-2">
      {ordered.slice(0, MAX_VISIBLE).map((execution) => {
        const timestamp = execution.completedAt ?? execution.startedAt ?? execution.createdAt;
        return (
          <li key={execution.id}>
            <button type="button" onClick={() => onSelect(execution)} className="block w-full text-left">
              <Card className={cn("hover:border-muted-foreground/50 transition-colors", selectedExecutionId === execution.id && "border-primary")}>
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
            </button>
          </li>
        );
      })}
      {executions.length > MAX_VISIBLE && (
        <p className="text-muted-foreground text-center text-xs">+{executions.length - MAX_VISIBLE} more</p>
      )}
    </ul>
  );
}
