"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/forms/switch";
import { Dialog } from "@/components/overlays/dialog";
import { ConnectionTestPanel } from "@/features/settings/components/connection-test-panel";
import { ConnectorConfigForm } from "@/features/settings/components/connector-config-form";
import { ConnectorCredentialSection } from "@/features/settings/components/connector-credential-section";
import { useRemoveConnector, useSetConnectorEnabled } from "@/features/settings/hooks/use-integrations";
import type { Connector } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * §11/§12: identity/status → configuration → test connection →
 * credential, matching the prompt's own recommended grouping as
 * closely as the real, ungrouped `config` schema allows (see
 * `ConnectorConfigForm`'s own docstring for why "Connection/
 * Authentication/Options" grouping isn't built).
 */
export function ConnectorDetailView({ connector }: { connector: Connector }) {
  const router = useRouter();
  const setEnabled = useSetConnectorEnabled(connector.id);
  const removeConnector = useRemoveConnector();
  const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false);

  async function handleToggleEnabled(enabled: boolean) {
    try {
      await setEnabled.mutateAsync(enabled);
      toast.success(enabled ? "Connector enabled" : "Connector disabled");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not change connector state", message);
    }
  }

  async function handleRemove() {
    try {
      await removeConnector.mutateAsync(connector.id);
      toast.success("Connector removed");
      setConfirmRemoveOpen(false);
      router.push("/settings/integrations");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not remove connector", message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>{connector.name}</CardTitle>
            <p className="text-muted-foreground text-sm">
              {connector.category} · {connector.connectorType} · {connector.authMethod}
            </p>
          </div>
          <StatusBadge tone={connector.status === "removed" ? "danger" : "info"} label={connector.status} />
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={connector.enabled} onChange={(event) => void handleToggleEnabled(event.target.checked)} aria-label="Enabled" />
            Enabled
          </label>
          {connector.consecutiveFailures > 0 && (
            <span className="text-warning text-xs">{connector.consecutiveFailures} consecutive failures</span>
          )}
          <Button variant="danger" onClick={() => setConfirmRemoveOpen(true)} className="ml-auto">
            Remove connector
          </Button>
        </CardContent>
      </Card>

      <ConnectorConfigForm connectorId={connector.id} config={connector.config} />
      <ConnectionTestPanel connectorId={connector.id} />
      <ConnectorCredentialSection connectorId={connector.id} />

      <Dialog
        open={confirmRemoveOpen}
        onClose={() => setConfirmRemoveOpen(false)}
        title={`Remove ${connector.name}?`}
        description="This is a soft removal — the connector moves to a removed state and is disabled. It stops appearing in the integrations list."
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmRemoveOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void handleRemove()} loading={removeConnector.isPending}>
              Remove connector
            </Button>
          </>
        }
      />
    </div>
  );
}
