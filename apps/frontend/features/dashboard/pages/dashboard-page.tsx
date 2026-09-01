"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { IconButton } from "@/components/ui/icon-button";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { PageHeader } from "@/components/navigation/page-header";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { AssetHealthSection } from "@/features/dashboard/components/asset-health-section";
import { AttentionRequiredSection } from "@/features/dashboard/components/attention-required-section";
import { DashboardCustomizeMenu } from "@/features/dashboard/components/dashboard-customize-menu";
import { DashboardModeTabs } from "@/features/dashboard/components/dashboard-mode-tabs";
import { GatewayLivenessCard } from "@/features/dashboard/components/gateway-liveness-card";
import { HealthOverviewSection } from "@/features/dashboard/components/health-overview-section";
import { KpiGrid } from "@/features/dashboard/components/kpi-grid";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { QuickAccessGrid } from "@/features/dashboard/components/quick-access-grid";
import { RecentActivitySection } from "@/features/dashboard/components/recent-activity-section";
import { SectionState } from "@/features/dashboard/components/section-state";
import { SystemStatusSection } from "@/features/dashboard/components/system-status-section";
import { computePlatformHealthTier } from "@/features/dashboard/lib/asset-health";
import { type DashboardModeValue, filterVisibleWidgets } from "@/features/dashboard/lib/widget-registry";
import { useInventoryStatistics } from "@/features/infrastructure/hooks/use-statistics";
import { resolveStatus } from "@/lib/status";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { usePermissions } from "@/permissions/hooks";
import { useDashboardPreferencesStore } from "@/state/dashboard-preferences-store";

/** `viewAllHref` only ever points at a route registered as
 * `"implemented"` in `lib/route-registry.ts` (§26: "only link to
 * routes that actually exist") — Monitoring (Prompt 006) and Alerting
 * (Prompt 007) shipped, so these sections finally have somewhere real
 * to send the operator for the fuller view. */
function SectionHeading({
  children,
  viewAllHref,
  viewAllLabel,
}: {
  children: React.ReactNode;
  viewAllHref?: string;
  viewAllLabel?: string;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className={typography.cardTitle}>{children}</h2>
      {viewAllHref && (
        <Link href={viewAllHref} className="text-primary text-xs font-medium hover:underline">
          {viewAllLabel ?? "View in Monitoring"}
        </Link>
      )}
    </div>
  );
}

function parseMode(value: string | null): DashboardModeValue | null {
  return value === "executive" || value === "operations" ? value : null;
}

/**
 * The Enterprise Dashboard / Executive Command Center (Prompt 020). An
 * orchestration layer only (§2): every widget below is a thin consumer
 * of a feature query/component this codebase already built for its own
 * page — Alerting's alerts, Automation's executions, Infrastructure's
 * inventory statistics, Audit's compliance trail (Prompt 015),
 * Notifications' recent page (Prompt 016), Reporting's statistics,
 * ai-assistant's recommendations — never a second, dashboard-owned
 * implementation of any of them. See
 * `docs/frontend/developer-guide/dashboard.md` for the full
 * architecture and the citation table behind every "confirmed absent"
 * decision below.
 *
 * Six sections are foundational to BOTH Executive and Operations mode
 * and always render regardless of mode/personalization (§5: "use the
 * same underlying data... do not create two separate applications"):
 * Executive Summary (`KpiGrid`), Asset Health, Active Alerts
 * (`AttentionRequiredSection`), Automation Status
 * (`RecentActivitySection`), System Status, and Quick Access. Making
 * these hideable would let a user configure away the platform's own
 * primary risk signals — the six *optional* widgets in
 * `features/dashboard/lib/widget-registry.ts` (Recent Activity,
 * Infrastructure, Notifications, Reporting, AI Insight, Operations
 * Workspace) are the ones §24/§26 apply to.
 */
export function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    organizations,
    isLoading: organizationsLoading,
    isError: organizationsError,
    selectedOrganizationId,
    needsSelection,
    hasNoAccess,
  } = useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const { role } = usePermissions();

  const preferredMode = useDashboardPreferencesStore((state) => state.preferredMode);
  const setPreferredMode = useDashboardPreferencesStore((state) => state.setPreferredMode);
  const hiddenWidgetIds = useDashboardPreferencesStore((state) => state.hiddenWidgetIds);
  const mode: DashboardModeValue = parseMode(searchParams.get("mode")) ?? preferredMode;

  function handleModeChange(nextMode: DashboardModeValue) {
    setPreferredMode(nextMode);
    const params = new URLSearchParams(searchParams.toString());
    params.set("mode", nextMode);
    router.push(`/?${params.toString()}`);
  }

  // Same `queryKey` `AssetHealthSection`/`InfrastructureOverviewWidget`
  // read below — React Query dedupes (§36), so the header's own health
  // badge costs nothing extra.
  const inventoryStatisticsQuery = useInventoryStatistics(selectedOrganizationId);
  const platformHealthTier = computePlatformHealthTier(inventoryStatisticsQuery.data?.healthDistribution);

  const scopeName = organizations?.find((org) => org.id === selectedOrganizationId)?.displayName;
  const visibleWidgets = selectedOrganizationId
    ? filterVisibleWidgets({ mode, role, hiddenWidgetIds })
    : [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="AI Infrastructure OS"
        title="Dashboard"
        description={scopeName ? `Executive Command Center for ${scopeName}.` : "Platform overview and operational health."}
        status={
          platformHealthTier !== null ? (
            <StatusIndicator state={platformHealthTier} label={`Platform ${resolveStatus(platformHealthTier).label}`} />
          ) : undefined
        }
        secondaryActions={
          <>
            <span className="text-muted-foreground hidden text-xs sm:inline">
              Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
            </span>
            <AskAiButton draft="Summarize the current state of active alerts, automation activity, and asset health." />
          </>
        }
        primaryAction={
          <IconButton
            icon={RefreshCw}
            aria-label="Refresh dashboard"
            variant="outline"
            loading={isRefreshing}
            onClick={refresh}
          />
        }
        overflowActions={<DashboardCustomizeMenu />}
      />

      <DashboardModeTabs mode={mode} onChange={handleModeChange} />

      <SectionState
        isLoading={organizationsLoading}
        isError={organizationsError}
        skeletonClassName="h-24 w-full"
      >
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Overview</SectionHeading>
              <KpiGrid organizationId={selectedOrganizationId} />
            </section>

            <AssetHealthSection organizationId={selectedOrganizationId} />

            <section>
              <SectionHeading viewAllHref="/monitoring">Operational health</SectionHeading>
              <HealthOverviewSection organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <section>
                <SectionHeading viewAllHref="/alerting/alerts" viewAllLabel="View in Alerting">
                  Attention required
                </SectionHeading>
                <AttentionRequiredSection organizationId={selectedOrganizationId} />
              </section>

              <section>
                <SectionHeading viewAllHref="/automation/executions" viewAllLabel="View in Automation">
                  Recent automation activity
                </SectionHeading>
                <RecentActivitySection organizationId={selectedOrganizationId} />
              </section>
            </div>

            <section>
              <SectionHeading viewAllHref="/monitoring/services">System status</SectionHeading>
              <SystemStatusSection organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading>Quick access</SectionHeading>
              <QuickAccessGrid />
            </section>

            {visibleWidgets.length > 0 && (
              <section>
                <SectionHeading>Additional insights</SectionHeading>
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
                  {visibleWidgets.map((widget) => {
                    const Widget = widget.component;
                    return <Widget key={widget.id} organizationId={selectedOrganizationId} />;
                  })}
                </div>
              </section>
            )}
          </div>
        )}
      </SectionState>

      <div className="max-w-xs">
        <GatewayLivenessCard />
      </div>
    </div>
  );
}
