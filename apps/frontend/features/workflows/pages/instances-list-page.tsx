"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { WorkflowsSubNav } from "@/features/workflows/components/workflows-sub-nav";
import { useWorkflowInstances, useWorkflows } from "@/features/workflows/hooks/use-workflows";
import { INSTANCE_STATUS_TO_STATUS } from "@/features/workflows/lib/status-maps";
import { WORKFLOW_INSTANCE_STATUSES, type WorkflowInstanceStatusValue } from "@/features/workflows/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** Every workflow instance for this organization. `status` is a real
 * server-side `GET /workflow-instances` parameter. */
export function InstancesListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const status = (searchParams.get("status") as WorkflowInstanceStatusValue | null) ?? "";
  const query = useWorkflowInstances(selectedOrganizationId, status || undefined);
  const workflowsQuery = useWorkflows(selectedOrganizationId);

  const workflowNameById = useMemo(
    () => new Map((workflowsQuery.data ?? []).map((workflow) => [workflow.id, workflow.name])),
    [workflowsQuery.data],
  );

  const updateStatus = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) params.set("status", value);
      else params.delete("status");
      router.push(`/workflows/instances?${params.toString()}`);
    },
    [router, searchParams],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Workflow instances"
        description="Every workflow run recorded for this organization."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={<IconButton icon={RefreshCw} aria-label="Refresh instances" variant="outline" loading={isRefreshing} onClick={refresh} />}
      />
      <WorkflowsSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="instance-status-filter">Status</Label>
              <Select
                id="instance-status-filter"
                value={status}
                onChange={(event) => updateStatus(event.target.value)}
                className="w-44"
              >
                <option value="">All statuses</option>
                {WORKFLOW_INSTANCE_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {value.replace(/_/g, " ")}
                  </option>
                ))}
              </Select>
            </div>

            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (query.data.length === 0 ? (
                  <EmptyState
                    title="No instances found"
                    description={status ? "Try clearing the status filter." : "No workflow has been run for this organization yet."}
                  />
                ) : (
                  <ul className="flex flex-col gap-2">
                    {query.data.map((instance) => (
                      <li key={instance.id}>
                        <Link href={`/workflows/instances/${instance.id}`} className="block">
                          <Card className="hover:border-muted-foreground/50 transition-colors">
                            <CardContent className="flex items-center justify-between gap-3 p-3">
                              <div className="flex flex-col gap-0.5">
                                <p className="text-sm font-medium">
                                  {workflowNameById.get(instance.definitionId) ?? `Run ${instance.id.slice(0, 8)}`}
                                </p>
                                <p className="text-muted-foreground text-xs">
                                  {instance.triggerType} ·{" "}
                                  {instance.startedAt ? (
                                    <time dateTime={instance.startedAt}>{formatRelativeTime(instance.startedAt)}</time>
                                  ) : (
                                    "not started"
                                  )}
                                </p>
                              </div>
                              <StatusIndicator state={INSTANCE_STATUS_TO_STATUS[instance.status]} />
                            </CardContent>
                          </Card>
                        </Link>
                      </li>
                    ))}
                  </ul>
                ))}
            </SectionState>
          </div>
        )}
      </SectionState>
    </div>
  );
}
