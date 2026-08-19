"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { useAssignCredential, useRotateCredential } from "@/features/settings/hooks/use-integrations";
import type { ConnectorCredential } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `POST /integrations/credentials`, `POST /integrations/credentials/{id}/rotate`.
 * **No route lists a connector's existing credentials** (confirmed
 * absent: `CredentialService.list_for_connector` has zero routes) —
 * this section can only track a credential it assigned *in this
 * browser session*; it cannot show credentials assigned earlier or
 * from elsewhere. The secret value itself is never returned by any
 * route here, not even masked (confirmed absent from the response
 * schema) — only a `secretRef` pointer.
 */
export function ConnectorCredentialSection({ connectorId }: { connectorId: string }) {
  const assignCredential = useAssignCredential(connectorId);
  const rotateCredential = useRotateCredential(connectorId);
  const [credential, setCredential] = useState<ConnectorCredential | null>(null);
  const [credentialType, setCredentialType] = useState("api_key");
  const [rawValue, setRawValue] = useState("");
  const [rotateValue, setRotateValue] = useState("");

  async function handleAssign(event: React.FormEvent) {
    event.preventDefault();
    try {
      const result = await assignCredential.mutateAsync({ connectorId, credentialType, rawValue: rawValue || undefined });
      setCredential(result);
      setRawValue("");
      toast.success("Credential assigned");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not assign credential", message);
    }
  }

  async function handleRotate(event: React.FormEvent) {
    event.preventDefault();
    if (!credential) return;
    try {
      const result = await rotateCredential.mutateAsync({ credentialId: credential.id, rawValue: rotateValue });
      setCredential(result);
      setRotateValue("");
      toast.success("Credential rotated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not rotate credential", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Credential</CardTitle>
        <CardDescription>
          No route lists credentials already assigned to this connector — only one assigned in this session is shown here.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!credential ? (
          <form onSubmit={handleAssign} className="flex flex-col gap-3">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField label="Credential type" required>
                {(fieldProps) => <Input {...fieldProps} value={credentialType} onChange={(event) => setCredentialType(event.target.value)} required />}
              </FormField>
              <FormField label="Secret value" description="Never displayed again after this save.">
                {(fieldProps) => <Input {...fieldProps} type="password" value={rawValue} onChange={(event) => setRawValue(event.target.value)} autoComplete="off" />}
              </FormField>
            </div>
            <Button type="submit" loading={assignCredential.isPending} className="w-fit">
              Assign credential
            </Button>
          </form>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-sm">
              Type <span className="font-medium">{credential.credentialType}</span> · Status {credential.status}
              {credential.lastRotatedAt && ` · Rotated ${new Date(credential.lastRotatedAt).toLocaleString()}`}
            </p>
            <form onSubmit={handleRotate} className="flex items-end gap-2">
              <FormField label="New secret value">
                {(fieldProps) => <Input {...fieldProps} type="password" value={rotateValue} onChange={(event) => setRotateValue(event.target.value)} autoComplete="off" />}
              </FormField>
              <Button type="submit" variant="outline" loading={rotateCredential.isPending} disabled={!rotateValue}>
                Rotate
              </Button>
            </form>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
