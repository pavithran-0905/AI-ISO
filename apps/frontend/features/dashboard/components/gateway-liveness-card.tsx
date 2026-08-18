"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { useGatewayLiveness } from "@/features/dashboard/hooks/use-gateway-liveness";

/**
 * The original `modules/dashboard` placeholder's card, migrated
 * verbatim (same markup/behavior, same tests ported) and deliberately
 * given the lowest visual weight on the page (§5: "the most important
 * information must be visually dominant") — it reports gateway
 * liveness, not the real per-service operational health that
 * `HealthOverviewSection`/`SystemStatusSection` now cover with actual
 * V1 data.
 */
export function GatewayLivenessCard() {
  const { data, isLoading, isError, error } = useGatewayLiveness();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Gateway</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground text-sm">Checking gateway status…</p>}

        {isError && (
          <div className="space-y-1">
            <StatusBadge tone="danger" label="Unreachable" />
            <p className="text-muted-foreground text-sm">
              {error instanceof Error ? error.message : "Could not reach the gateway."}
            </p>
          </div>
        )}

        {data && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div className="col-span-2">
              <StatusBadge tone="success" label={data.status} />
            </div>
            <dt className="text-muted-foreground">Service</dt>
            <dd>{data.service}</dd>
            <dt className="text-muted-foreground">Version</dt>
            <dd>{data.version}</dd>
            <dt className="text-muted-foreground">Environment</dt>
            <dd>{data.environment}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
