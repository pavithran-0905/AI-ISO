"use client";

import { RefreshCw, Sparkles } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { IconButton } from "@/components/ui/icon-button";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { SEVERITY_RANK } from "@/features/alerting/lib/severity";
import { RESOLVED_ALERT_STATUSES, type Alert } from "@/features/alerting/types";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import type { AutomationExecution } from "@/features/automation/types";
import { AlertContextPanel } from "@/features/operations/components/alert-context-panel";
import { AlertSignalsList } from "@/features/operations/components/alert-signals-list";
import { AutomationSignalsList } from "@/features/operations/components/automation-signals-list";
import { ExecutionContextPanel } from "@/features/operations/components/execution-context-panel";
import { RecentActivityTimeline } from "@/features/operations/components/recent-activity-timeline";
import { parseSignalParam, signalRefToParam } from "@/features/operations/types";
import { EmptyState } from "@/components/feedback/empty-state";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";
import { useSelectedOrganization } from "@/organization/use-organizations";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Operations Workspace — `/operations` (§4). A frontend-only
 * correlation view over Alerting and Automation's own real data
 * (§2: no incident entity/database/API exists in Backend V1, and none
 * is fabricated here). The selected signal lives entirely in the URL
 * (`?signal=alert:<id>` / `execution:<id>`) rather than local state,
 * derived from the same already-loaded lists the signal columns
 * render — so reloading or sharing the URL reopens the same
 * investigation context (§25/§26), and no second fetch is needed to
 * resolve a selection. See
 * `docs/frontend/developer-guide/operations-workspace.md` for exactly
 * which correlations are real (alert-to-alert correlation,
 * execution-to-target-id) versus confirmed absent (alert-to-resource,
 * execution-to-verified-resource, any resource-to-audit link).
 */
export function OperationsWorkspacePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const signal = parseSignalParam(searchParams.get("signal"));

  const alertsQuery = useAlerts(selectedOrganizationId ? { organizationId: selectedOrganizationId } : null);
  const executionsQuery = useExecutions(selectedOrganizationId ? { organizationId: selectedOrganizationId } : null);

  const activeAlerts = (alertsQuery.data ?? []).filter((alert) => !RESOLVED_ALERT_STATUSES.has(alert.status));
  const highestSeverity = activeAlerts.length > 0 ? [...activeAlerts].sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity])[0].severity : null;

  const selectedAlert: Alert | null = signal?.kind === "alert" ? (alertsQuery.data?.find((alert) => alert.id === signal.id) ?? null) : null;
  const selectedExecution: AutomationExecution | null = signal?.kind === "execution" ? (executionsQuery.data?.find((execution) => execution.id === signal.id) ?? null) : null;

  function selectAlert(alert: Alert) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("signal", signalRefToParam({ kind: "alert", id: alert.id }));
    router.push(`/operations?${params.toString()}`);
  }

  function selectExecution(execution: AutomationExecution) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("signal", signalRefToParam({ kind: "execution", id: execution.id }));
    router.push(`/operations?${params.toString()}`);
  }

  async function scopedRefresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["alerts"] }),
      queryClient.invalidateQueries({ queryKey: ["automation", "executions"] }),
      queryClient.invalidateQueries({ queryKey: ["audit"] }),
    ]);
    await refresh();
  }

  const investigateDraft = `Summarize the current operational situation: ${activeAlerts.length} active alert${activeAlerts.length === 1 ? "" : "s"}${
    highestSeverity ? ` (highest severity: ${highestSeverity})` : ""
  }.`;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Operations Workspace"
        description="Investigate active alerts and recent automation activity in one place — not a backend incident system."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <div className="flex items-center gap-2">
            <AskAiButton draft={investigateDraft} />
            <IconButton icon={RefreshCw} aria-label="Refresh operations data" variant="outline" loading={isRefreshing} onClick={() => void scopedRefresh()} />
          </div>
        }
      />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
            <div className="flex flex-col gap-8">
              {!alertsQuery.isLoading && activeAlerts.length === 0 && !signal && (
                <EmptyState title="No active issues detected in this scope" description="Nothing currently needs attention." />
              )}

              <section>
                <SectionHeading>Active alerts</SectionHeading>
                <AlertSignalsList organizationId={selectedOrganizationId} selectedAlertId={selectedAlert?.id ?? null} onSelect={selectAlert} />
              </section>

              <section>
                <SectionHeading>Automation activity</SectionHeading>
                <AutomationSignalsList organizationId={selectedOrganizationId} selectedExecutionId={selectedExecution?.id ?? null} onSelect={selectExecution} />
              </section>

              <section>
                <RecentActivityTimeline organizationId={selectedOrganizationId} />
              </section>
            </div>

            <aside className="flex flex-col gap-4">
              <SectionHeading>Investigation</SectionHeading>
              {selectedAlert && <AlertContextPanel alert={selectedAlert} />}
              {selectedExecution && <ExecutionContextPanel execution={selectedExecution} />}
              {!selectedAlert && !selectedExecution && (
                <EmptyState icon={Sparkles} title="Nothing selected" description="Select an alert or automation run to investigate it here." />
              )}
            </aside>
          </div>
        )}
      </SectionState>
    </div>
  );
}
