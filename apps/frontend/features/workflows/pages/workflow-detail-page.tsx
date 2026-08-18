"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { SectionState } from "@/features/dashboard/components/section-state";
import { WorkflowActions } from "@/features/workflows/components/workflow-actions";
import { useWorkflow, useWorkflowInstances } from "@/features/workflows/hooks/use-workflows";
import { INSTANCE_STATUS_TO_STATUS } from "@/features/workflows/lib/status-maps";
import { formatRelativeTime } from "@/lib/relative-time";

const RECENT_LIMIT = 10;

/** Workflow Detail — `/workflows/[id]`. Recent instances are filtered
 * client-side from the org-wide list, which the endpoint returns
 * complete and unpaginated (there is no per-definition instance
 * route). */
export function WorkflowDetailPage({ workflowId }: { workflowId: string }) {
  const router = useRouter();
  const query = useWorkflow(workflowId);
  const instancesQuery = useWorkflowInstances(query.data?.organizationId ?? null);

  const instances = useMemo(
    () => (instancesQuery.data ?? []).filter((instance) => instance.definitionId === workflowId).slice(0, RECENT_LIMIT),
    [instancesQuery.data, workflowId],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.name ?? "Workflow"}
        description={query.data?.workflowKey}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/workflows")}>
            Back to Workflows
          </Button>
        }
      />

      <SectionState
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => query.refetch()}
        skeletonClassName="h-96 w-full"
      >
        {query.data && (
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Identity</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
                  <div className="flex flex-col gap-0.5">
                    <dt className="text-muted-foreground text-xs">Key</dt>
                    <dd className="font-mono text-xs">{query.data.workflowKey}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <dt className="text-muted-foreground text-xs">Current version</dt>
                    <dd className="text-sm">{query.data.currentVersionNumber ?? "—"}</dd>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <dt className="text-muted-foreground text-xs">Owner</dt>
                    <dd className="text-sm">{query.data.owner ?? "—"}</dd>
                  </div>
                </dl>
                {query.data.description && <p className="text-muted-foreground text-sm">{query.data.description}</p>}
                {query.data.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {query.data.tags.map((tag) => (
                      <Badge key={tag} variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <WorkflowActions workflow={query.data} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Default variables</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(query.data.defaultVariables).length === 0 ? (
                  <p className="text-muted-foreground text-sm">No default variables.</p>
                ) : (
                  <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                    {Object.entries(query.data.defaultVariables).map(([key, value]) => (
                      <div key={key} className="flex flex-col gap-0.5">
                        <dt className="text-muted-foreground font-mono text-xs">{key}</dt>
                        <dd className="font-mono text-xs">{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Recent instances</CardTitle>
              </CardHeader>
              <CardContent>
                <SectionState
                  isLoading={instancesQuery.isLoading}
                  isError={instancesQuery.isError}
                  error={instancesQuery.error}
                  onRetry={() => instancesQuery.refetch()}
                >
                  {instancesQuery.data &&
                    (instances.length === 0 ? (
                      <EmptyState title="No instances yet" description="This workflow hasn't been run." />
                    ) : (
                      <ul className="flex flex-col gap-2">
                        {instances.map((instance) => (
                          <li key={instance.id}>
                            <Link href={`/workflows/instances/${instance.id}`} className="block">
                              <Card className="hover:border-muted-foreground/50 transition-colors">
                                <CardContent className="flex items-center justify-between gap-3 p-3">
                                  <div className="flex flex-col gap-0.5">
                                    <p className="text-sm font-medium">Run {instance.id.slice(0, 8)}</p>
                                    <p className="text-muted-foreground text-xs">
                                      {instance.startedAt ? (
                                        <time dateTime={instance.startedAt}>{formatRelativeTime(instance.startedAt)}</time>
                                      ) : (
                                        "Not started"
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
              </CardContent>
            </Card>
          </div>
        )}
      </SectionState>
    </div>
  );
}
