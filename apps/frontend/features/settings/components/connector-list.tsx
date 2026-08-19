"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import type { Connector, ConnectorLifecycleStatusValue } from "@/features/settings/types";

const STATUS_TONE: Record<ConnectorLifecycleStatusValue, "neutral" | "info" | "success" | "warning" | "danger"> = {
  registered: "neutral",
  installed: "info",
  configured: "info",
  validated: "success",
  enabled: "success",
  disabled: "neutral",
  deprecated: "warning",
  removed: "danger",
};

export function ConnectorList({ connectors }: { connectors: Connector[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {connectors.map((connector) => (
        <li key={connector.id}>
          <Link href={`/settings/integrations/${connector.id}`} className="block">
            <Card className="hover:border-muted-foreground/50 transition-colors">
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-medium">{connector.name}</p>
                  <p className="text-muted-foreground text-xs">
                    {connector.category} · {connector.connectorType}
                    {connector.lastValidatedAt ? ` · Verified ${new Date(connector.lastValidatedAt).toLocaleDateString()}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {connector.enabled && <StatusBadge tone="success" label="Enabled" />}
                  <StatusBadge tone={STATUS_TONE[connector.status]} label={connector.status} />
                </div>
              </CardContent>
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  );
}
