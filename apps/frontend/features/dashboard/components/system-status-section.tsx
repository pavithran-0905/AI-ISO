"use client";

import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useGatewayHealth } from "@/features/dashboard/hooks/use-gateway-health";
import type { HealthStateValue } from "@/features/dashboard/types";
import type { StatusState } from "@/lib/status";

const HEALTH_STATE_TO_STATUS: Record<HealthStateValue, StatusState> = {
  healthy: "healthy",
  degraded: "degraded",
  warning: "warning",
  unhealthy: "critical",
  maintenance: "maintenance",
  unknown: "unknown",
};

/**
 * System Status (§11, Level 5) — the same `GET /gateway/health` call as
 * `HealthOverviewSection` (React Query dedupes the request; both read
 * from one cache entry), shown here per-instance rather than
 * aggregated. Never claims a service is healthy "because the page
 * loaded" (§11) — every row is the backend's own, individually probed
 * `status`.
 */
export function SystemStatusSection({ organizationId }: { organizationId: string }) {
  const query = useGatewayHealth(organizationId);

  return (
    <SectionState
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-32 w-full"
    >
      {query.data &&
        (query.data.instances.length === 0 ? (
          <EmptyState title="No registered services yet" description="Nothing has been registered with the gateway for this organization." />
        ) : (
          <ul className="divide-border border-border divide-y rounded-lg border">
            {query.data.instances.map((instance) => (
              <li key={instance.serviceId + instance.instanceUrl} className="flex items-center justify-between gap-3 p-3 text-sm">
                <span className="truncate font-mono text-xs">{instance.instanceUrl}</span>
                <span className="flex items-center gap-2">
                  {instance.latencyMs !== null && (
                    <span className="text-muted-foreground text-xs">{Math.round(instance.latencyMs)}ms</span>
                  )}
                  <StatusIndicator state={HEALTH_STATE_TO_STATUS[instance.status]} />
                </span>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
