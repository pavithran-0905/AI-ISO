"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { PageHeader } from "@/components/navigation/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { Card, CardContent } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { StatusBadge } from "@/components/feedback/status-badge";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ReportingSubNav } from "@/features/reporting/components/reporting-sub-nav";
import { useTemplates } from "@/features/reporting/hooks/use-templates";
import { TEMPLATE_STATUS_TONE } from "@/features/reporting/lib/status-tones";
import { usePermissions } from "@/permissions/hooks";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { formatRelativeTime } from "@/lib/relative-time";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** Every template version for this organization (§7). `GET /reports/templates`
 * returns every version of every template (not just the latest) — grouped
 * here isn't attempted since the backend gives no "latest version"
 * marker beyond what's already visible per row. */
export function TemplatesListPage() {
  const router = useRouter();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const { can } = usePermissions();
  const query = useTemplates(selectedOrganizationId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Templates"
        description="Reusable report definitions, versioned and approved before use."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <div className="flex items-center gap-2">
            <IconButton icon={RefreshCw} aria-label="Refresh templates" variant="outline" loading={isRefreshing} onClick={refresh} />
            {can("create") && (
              <Button onClick={() => router.push("/reporting/templates/new")} className="gap-1.5">
                <Plus className="size-4" aria-hidden="true" />
                New template
              </Button>
            )}
          </div>
        }
      />
      <ReportingSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
            {query.data &&
              (query.data.length === 0 ? (
                <EmptyState
                  title="No report templates available"
                  description="Create a template to design a reusable report structure."
                  action={
                    can("create") ? (
                      <Link href="/reporting/templates/new" className="text-primary text-sm font-medium hover:underline">
                        New template
                      </Link>
                    ) : undefined
                  }
                />
              ) : (
                <ul className="flex flex-col gap-2">
                  {query.data.map((template) => (
                    <li key={template.id}>
                      <Link href={`/reporting/templates/${template.id}`} className="block">
                        <Card className="hover:border-muted-foreground/50 transition-colors">
                          <CardContent className="flex items-center justify-between gap-3 p-3">
                            <div className="flex flex-col gap-0.5">
                              <p className="text-sm font-medium">
                                {template.name} <span className="text-muted-foreground font-normal">v{template.versionNumber}</span>
                              </p>
                              <p className="text-muted-foreground text-xs">
                                {template.category} · {template.reportType}
                              </p>
                            </div>
                            <StatusBadge tone={TEMPLATE_STATUS_TONE[template.status]} label={template.status} />
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
