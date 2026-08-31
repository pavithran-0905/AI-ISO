"use client";

import { RefreshCw } from "lucide-react";

import { Alert } from "@/components/feedback/alert";
import { PageHeader } from "@/components/navigation/page-header";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AuditSubNav } from "@/features/audit/components/audit-sub-nav";
import { AuditSummaryWidget } from "@/features/audit/components/audit-summary-widget";
import { FindingsSummaryWidget } from "@/features/audit/components/findings-summary-widget";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Audit & Activity Overview — `/audit` (§6). There is no platform-wide
 * audit log to summarize: this shows `compliance-service`'s own real
 * summary (the primary/richest of the three real sources) plus a real
 * compliance-posture signal, never an invented cross-service total.
 * See `docs/frontend/developer-guide/audit-activity.md`.
 */
export function AuditOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Audit & Activity"
        description="Cross-service audit trails and compliance posture."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh audit data" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <AuditSubNav />

      <Alert tone="warning" title="No platform-wide audit log exists">
        This shows three real, separately-scoped audit trails (compliance, integrations, notifications) — never merged
        into one feed. Six other services record audit-shaped data with no route to read it back. See the developer
        guide for the full breakdown.
      </Alert>

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Compliance audit activity (30 days)</SectionHeading>
              <AuditSummaryWidget organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading>Compliance posture</SectionHeading>
              <FindingsSummaryWidget organizationId={selectedOrganizationId} />
            </section>
          </div>
        )}
      </SectionState>
    </div>
  );
}
