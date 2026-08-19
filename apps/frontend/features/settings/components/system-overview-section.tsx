"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAdminDashboard, useSystemHealth } from "@/features/settings/hooks/use-system-settings";
import type { StatusState } from "@/lib/status";

/** `GET /admin/dashboard`, `GET /admin/health` — both read-only, no
 * role check on either route (any authenticated user of the org could
 * call these directly; this page itself is only reachable from the
 * nav for administrators — see `nav-items.ts`). */
export function SystemOverviewSection() {
  const dashboardQuery = useAdminDashboard();
  const healthQuery = useSystemHealth();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Overview</CardTitle>
        <CardDescription>A point-in-time snapshot across every tenant.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <SectionState isLoading={dashboardQuery.isLoading} isError={dashboardQuery.isError} error={dashboardQuery.error} onRetry={() => dashboardQuery.refetch()}>
          {dashboardQuery.data && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              <Stat label="Tenants" value={dashboardQuery.data.tenantCount} />
              <Stat label="Active tenants" value={dashboardQuery.data.activeTenantCount} />
              <Stat label="Organizations" value={dashboardQuery.data.organizationCount} />
              <Stat label="Running jobs" value={dashboardQuery.data.runningJobCount} />
              <Stat label="Failed jobs" value={dashboardQuery.data.failedJobCount} />
              <Stat label="Open maintenance windows" value={dashboardQuery.data.openMaintenanceWindowCount} />
            </dl>
          )}
        </SectionState>

        <SectionState isLoading={healthQuery.isLoading} isError={healthQuery.isError} error={healthQuery.error} onRetry={() => healthQuery.refetch()}>
          {healthQuery.data && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground text-xs">Overall:</span>
                <StatusIndicator state={healthStateFor(healthQuery.data.overallStatus)} />
              </div>
              <ul className="flex flex-wrap gap-3 text-xs">
                {healthQuery.data.components.map((component) => (
                  <li key={component.component} className="flex items-center gap-1.5">
                    <StatusIndicator state={healthStateFor(component.status)} label={component.component} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </SectionState>
      </CardContent>
    </Card>
  );
}

function healthStateFor(status: string): StatusState {
  const normalized = status.toLowerCase();
  if (normalized === "healthy") return "healthy";
  if (normalized === "degraded" || normalized === "warning") return "warning";
  if (normalized === "unhealthy" || normalized === "critical") return "critical";
  return "unknown";
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value.toLocaleString()}</dd>
    </div>
  );
}
