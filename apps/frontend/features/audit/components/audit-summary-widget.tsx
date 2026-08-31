"use client";

import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { formatActionLabel } from "@/features/audit/lib/format";
import { useComplianceAuditSummary } from "@/features/audit/hooks/use-audit";

/** `GET /compliance/audit/summary` (§6) — the richest of the two real
 * summary endpoints (`notifications` has one too, but this Overview
 * shows compliance-service's since it's the primary/richest source —
 * see the developer guide). Only real backend-computed counts, never
 * a client-side tally over a partial page of results. */
export function AuditSummaryWidget({ organizationId }: { organizationId: string }) {
  const query = useComplianceAuditSummary(organizationId, 30);
  const topActions = query.data ? Object.entries(query.data.byAction).sort((a, b) => b[1] - a[1]).slice(0, 5) : [];

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard label="Total events (30d)" value={query.data.total} href="/audit/activity" />
            <MetricCard label="Distinct action types" value={Object.keys(query.data.byAction).length} />
          </div>
          {topActions.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <p className="text-muted-foreground text-xs">Most frequent actions</p>
              <ul className="flex flex-col gap-1">
                {topActions.map(([action, count]) => (
                  <li key={action} className="flex items-center justify-between text-sm">
                    <span>{formatActionLabel(action)}</span>
                    <span className="text-muted-foreground tabular-nums">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </SectionState>
  );
}
