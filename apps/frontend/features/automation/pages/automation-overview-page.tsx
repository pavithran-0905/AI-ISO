"use client";

import { RefreshCw } from "lucide-react";
import { useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AutomationSubNav } from "@/features/automation/components/automation-sub-nav";
import { AutomationSummary } from "@/features/automation/components/automation-summary";
import { ExecutionTable } from "@/features/automation/components/execution-table";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import { useAutomationJobs } from "@/features/automation/hooks/use-jobs";
import { ACTIVE_EXECUTION_STATUSES } from "@/features/automation/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

const RECENT_LIMIT = 8;

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Automation Overview (§4) — answers "what exists / what's running /
 * what failed / what completed recently" from real V1 data. The two
 * live sections are derived from the complete, unpaginated execution
 * list rather than from the statistics snapshot, because that snapshot
 * is computed once and never refreshed (see `AutomationSummary`).
 *
 * "What is scheduled?" is deliberately not answered: automation
 * schedules have no API and the service's cron engine is never
 * started — see `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function AutomationOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const executionsQuery = useExecutions(selectedOrganizationId ? { organizationId: selectedOrganizationId } : null);
  const jobsQuery = useAutomationJobs(selectedOrganizationId);

  const jobNameById = useMemo(
    () => new Map((jobsQuery.data ?? []).map((job) => [job.id, job.name])),
    [jobsQuery.data],
  );
  const activeExecutions = useMemo(
    () => (executionsQuery.data ?? []).filter((execution) => ACTIVE_EXECUTION_STATUSES.has(execution.status)).slice(0, RECENT_LIMIT),
    [executionsQuery.data],
  );
  const recentFailures = useMemo(
    () =>
      (executionsQuery.data ?? [])
        .filter((execution) => execution.status === "failed" || execution.status === "timed_out")
        .slice(0, RECENT_LIMIT),
    [executionsQuery.data],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Automation"
        description="Automation jobs, executions, and operational run history."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh automation data" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <AutomationSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Summary</SectionHeading>
              <AutomationSummary organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading>Running now</SectionHeading>
              <SectionState
                isLoading={executionsQuery.isLoading}
                isError={executionsQuery.isError}
                error={executionsQuery.error}
                onRetry={() => executionsQuery.refetch()}
              >
                {executionsQuery.data &&
                  (activeExecutions.length === 0 ? (
                    <EmptyState title="Nothing running" description="No automation is currently pending, running, or paused." />
                  ) : (
                    <ExecutionTable
                      executions={activeExecutions}
                      jobNameById={jobNameById}
                      sortField="createdAt"
                      sortDirection="desc"
                      onSortChange={() => undefined}
                    />
                  ))}
              </SectionState>
            </section>

            <section>
              <SectionHeading>Needs attention</SectionHeading>
              <SectionState
                isLoading={executionsQuery.isLoading}
                isError={executionsQuery.isError}
                error={executionsQuery.error}
                onRetry={() => executionsQuery.refetch()}
              >
                {executionsQuery.data &&
                  (recentFailures.length === 0 ? (
                    <EmptyState title="No recent failures" description="Nothing has failed or timed out." />
                  ) : (
                    <ExecutionTable
                      executions={recentFailures}
                      jobNameById={jobNameById}
                      sortField="createdAt"
                      sortDirection="desc"
                      onSortChange={() => undefined}
                    />
                  ))}
              </SectionState>
            </section>
          </div>
        )}
      </SectionState>
    </div>
  );
}
