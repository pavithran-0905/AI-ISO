"use client";

import { StatusBadge, type StatusTone } from "@/components/feedback/status-badge";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useFindingsSummary } from "@/features/audit/hooks/use-audit";
import type { FindingSeverityValue } from "@/features/audit/types";

const SEVERITY_TONES: Record<string, StatusTone> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "info",
  informational: "neutral",
};

/**
 * `GET /compliance/findings/summary` (§6's "Access Changes"/posture-
 * style metric) — a cheap compliance-posture signal, not full findings
 * management (out of this prompt's own IA; see
 * `docs/frontend/developer-guide/audit-activity.md`).
 */
export function FindingsSummaryWidget({ organizationId }: { organizationId: string }) {
  const query = useFindingsSummary(organizationId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard label="Open findings" value={query.data.openTotal} />
            <MetricCard label="Critical (open)" value={query.data.criticalOpen} />
            <MetricCard label="Overdue" value={query.data.overdue} />
          </div>
          {Object.keys(query.data.bySeverity).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(query.data.bySeverity).map(([severity, count]) => (
                <StatusBadge
                  key={severity}
                  tone={SEVERITY_TONES[severity as FindingSeverityValue] ?? "neutral"}
                  label={`${severity}: ${count}`}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </SectionState>
  );
}
