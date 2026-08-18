"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useMaintenanceWindows } from "@/features/alerting/hooks/use-maintenance-windows";
import { formatRelativeTime } from "@/lib/relative-time";

/**
 * Read-only — `alert-configuration.py` only exposes GET+POST for
 * maintenance windows, and creating one wasn't required by §9's
 * "represent them clearly" language. No creation form is built here;
 * see `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function MaintenanceWindowsList({ organizationId }: { organizationId: string }) {
  const query = useMaintenanceWindows(organizationId, true);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No active maintenance windows" description="Nothing is currently suppressing alerts for maintenance." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((window) => (
              <li key={window.id}>
                <Card>
                  <CardContent className="flex items-center justify-between gap-3 p-3">
                    <div className="flex flex-col gap-0.5">
                      <p className="text-sm font-medium">{window.name}</p>
                      <p className="text-muted-foreground text-xs">
                        {window.windowType} · {window.scope}
                        {window.scopeReference ? ` (${window.scopeReference})` : ""}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <StatusBadge tone={window.enabled ? "success" : "neutral"} label={window.enabled ? "Enabled" : "Disabled"} />
                      <p className="text-muted-foreground text-xs">
                        Ends <time dateTime={window.endsAt}>{formatRelativeTime(window.endsAt)}</time>
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
