"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useGatewayHealth } from "@/features/dashboard/hooks/use-gateway-health";
import type { HealthStateValue } from "@/features/dashboard/types";
import type { StatusState } from "@/lib/status";

/** `HealthState` (backend) → the canonical status taxonomy — kept as an
 * explicit map rather than reusing the string directly, since the two
 * vocabularies aren't identical (`unhealthy` has no 1:1 taxonomy
 * entry; it's the same severity tier as `critical`). */
const HEALTH_STATE_TO_STATUS: Record<HealthStateValue, StatusState> = {
  healthy: "healthy",
  degraded: "degraded",
  warning: "warning",
  unhealthy: "critical",
  maintenance: "maintenance",
  unknown: "unknown",
};

/**
 * Operational Health (§8, Level 2 of the information hierarchy) — the
 * aggregate of `GET /gateway/health`'s per-instance `status` values,
 * counted client-side from real, individually-typed data (not a
 * backend-provided summary field, which doesn't exist — see
 * `docs/frontend/developer-guide/dashboard.md`).
 */
export function HealthOverviewSection({ organizationId }: { organizationId: string }) {
  const query = useGatewayHealth(organizationId);

  return (
    <SectionState
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-20 w-full"
    >
      {query.data &&
        (query.data.instances.length === 0 ? (
          <EmptyState title="No registered services yet" description="Nothing has been registered with the gateway for this organization." />
        ) : (
          <HealthCounts instances={query.data.instances} />
        ))}
    </SectionState>
  );
}

function HealthCounts({ instances }: { instances: { status: HealthStateValue }[] }) {
  const counts = new Map<HealthStateValue, number>();
  for (const instance of instances) counts.set(instance.status, (counts.get(instance.status) ?? 0) + 1);

  const states: HealthStateValue[] = ["healthy", "warning", "degraded", "unhealthy", "maintenance", "unknown"];
  const present = states.filter((state) => counts.has(state));

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {present.map((state) => (
        <Card key={state}>
          <CardContent className="flex flex-col items-start gap-2 p-4">
            <StatusIndicator state={HEALTH_STATE_TO_STATUS[state]} />
            <p className="text-2xl font-semibold tabular-nums">{counts.get(state)}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
