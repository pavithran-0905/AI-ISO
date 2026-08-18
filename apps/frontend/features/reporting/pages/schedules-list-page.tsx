"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/navigation/page-header";
import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { StatusBadge } from "@/components/feedback/status-badge";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ReportingSubNav } from "@/features/reporting/components/reporting-sub-nav";
import { useSchedules } from "@/features/reporting/hooks/use-schedules";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** Every schedule across every report in this organization (§15) —
 * `GET /reports/schedules` with no `report_id` filter. Each row links
 * to its own report; managing (enable/disable/delete) a schedule
 * happens from that report's own detail page, which is where creation
 * lives too. */
export function SchedulesListPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const query = useSchedules(selectedOrganizationId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Scheduled Reports"
        description="Every recurring report schedule for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={<IconButton icon={RefreshCw} aria-label="Refresh schedules" variant="outline" loading={isRefreshing} onClick={refresh} />}
      />
      <ReportingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
            {query.data &&
              (query.data.length === 0 ? (
                <EmptyState title="No scheduled reports" description="Schedule a report from its own detail page." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {query.data.map((schedule) => (
                    <li key={schedule.id}>
                      <Link href={`/reporting/reports/${schedule.jobId}`} className="block">
                        <Card className="hover:border-muted-foreground/50 transition-colors">
                          <CardContent className="flex items-center justify-between gap-3 p-3">
                            <div className="flex flex-col gap-0.5">
                              <p className="text-sm font-medium">
                                {schedule.frequency.replace("_", " ")} · {schedule.timezone}
                              </p>
                              <p className="text-muted-foreground text-xs">
                                {schedule.nextRunAt ? (
                                  <>
                                    Next run <time dateTime={schedule.nextRunAt}>{formatRelativeTime(schedule.nextRunAt)}</time>
                                  </>
                                ) : (
                                  "No upcoming run"
                                )}
                              </p>
                            </div>
                            <StatusBadge tone={schedule.enabled ? "success" : "neutral"} label={schedule.enabled ? "Enabled" : "Disabled"} />
                          </CardContent>
                        </Card>
                      </Link>
                    </li>
                  ))}
                </ul>
              ))}
          </SectionState>
        )}
      </SectionState>
    </div>
  );
}
