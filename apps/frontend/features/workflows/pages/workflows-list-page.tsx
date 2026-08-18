"use client";

import { RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Badge } from "@/components/ui/badge";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { WorkflowsSubNav } from "@/features/workflows/components/workflows-sub-nav";
import { useWorkflows } from "@/features/workflows/hooks/use-workflows";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** Every workflow definition for this organization. Search is
 * client-side over the endpoint's complete, unpaginated result —
 * `GET /workflows` accepts only `organization_id`. */
export function WorkflowsListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const search = searchParams.get("q") ?? "";
  const query = useWorkflows(selectedOrganizationId);

  const updateSearch = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) params.set("q", value);
      else params.delete("q");
      router.push(`/workflows?${params.toString()}`);
    },
    [router, searchParams],
  );

  const visibleWorkflows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (query.data ?? []).filter(
      (workflow) =>
        !needle ||
        workflow.name.toLowerCase().includes(needle) ||
        workflow.workflowKey.toLowerCase().includes(needle) ||
        (workflow.description ?? "").toLowerCase().includes(needle),
    );
  }, [query.data, search]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Workflows"
        description="DAG workflow definitions and their execution history."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={<IconButton icon={RefreshCw} aria-label="Refresh workflows" variant="outline" loading={isRefreshing} onClick={refresh} />}
      />
      <WorkflowsSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <div className="flex min-w-48 max-w-md flex-col gap-1.5">
              <Label htmlFor="workflow-search">Search</Label>
              <div className="relative">
                <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
                <Input
                  id="workflow-search"
                  value={search}
                  onChange={(event) => updateSearch(event.target.value)}
                  placeholder="Name, key, or description…"
                  className="pl-9"
                />
              </div>
            </div>

            <SectionState
              isLoading={query.isLoading}
              isError={query.isError}
              error={query.error}
              onRetry={() => query.refetch()}
              skeletonClassName="h-96 w-full"
            >
              {query.data &&
                (visibleWorkflows.length === 0 ? (
                  <EmptyState
                    title={search ? "No matching workflows" : "No workflows defined"}
                    description={search ? "Try a different search term." : "Nothing has been defined for this organization yet."}
                  />
                ) : (
                  <ul className="flex flex-col gap-2">
                    {visibleWorkflows.map((workflow) => (
                      <li key={workflow.id}>
                        <Link href={`/workflows/${workflow.id}`} className="block">
                          <Card className="hover:border-muted-foreground/50 transition-colors">
                            <CardContent className="flex flex-wrap items-center justify-between gap-3 p-3">
                              <div className="flex flex-col gap-0.5">
                                <p className="text-sm font-medium">{workflow.name}</p>
                                <p className="text-muted-foreground font-mono text-xs">{workflow.workflowKey}</p>
                              </div>
                              <div className="flex items-center gap-2">
                                {workflow.tags.slice(0, 3).map((tag) => (
                                  <Badge key={tag} variant="outline">
                                    {tag}
                                  </Badge>
                                ))}
                                {workflow.currentVersionNumber && (
                                  <span className="text-muted-foreground text-xs">v{workflow.currentVersionNumber}</span>
                                )}
                              </div>
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
