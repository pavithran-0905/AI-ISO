"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Dialog } from "@/components/overlays/dialog";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { useCreateConnector } from "@/features/settings/hooks/use-integrations";
import { CONNECTOR_AUTH_METHODS, CONNECTOR_CATEGORIES, type ConnectorAuthMethodValue, type ConnectorCategoryValue } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `POST /integrations/connectors` — a generic connector framework, not
 * a set of named integrations (§10). No dedicated Ansible/Redfish/
 * Kubernetes category or form exists; `connectorType` is real free
 * text under one of the 15 real categories — see the developer guide's
 * "Why no specialized Ansible/Kubernetes form".
 */
export function CreateConnectorDialog({ organizationId, open, onClose }: { organizationId: string; open: boolean; onClose: () => void }) {
  const router = useRouter();
  const createConnector = useCreateConnector();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<ConnectorCategoryValue>("custom");
  const [connectorType, setConnectorType] = useState("");
  const [authMethod, setAuthMethod] = useState<ConnectorAuthMethodValue>("api_key");
  const [description, setDescription] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const connector = await createConnector.mutateAsync({
        organizationId,
        name,
        category,
        connectorType,
        authMethod,
        description: description || undefined,
      });
      toast.success("Connector registered");
      onClose();
      router.push(`/settings/integrations/${connector.id}`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not register connector", message);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Register a connector">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <FormField label="Name" required>
          {(fieldProps) => <Input {...fieldProps} value={name} onChange={(event) => setName(event.target.value)} required />}
        </FormField>
        <FormField label="Connector type" required description="Free text, e.g. kubernetes, ansible, redfish, slack.">
          {(fieldProps) => <Input {...fieldProps} value={connectorType} onChange={(event) => setConnectorType(event.target.value)} required />}
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Category" required>
            {(fieldProps) => (
              <Select {...fieldProps} value={category} onChange={(event) => setCategory(event.target.value as ConnectorCategoryValue)}>
                {CONNECTOR_CATEGORIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
          <FormField label="Auth method" required>
            {(fieldProps) => (
              <Select {...fieldProps} value={authMethod} onChange={(event) => setAuthMethod(event.target.value as ConnectorAuthMethodValue)}>
                {CONNECTOR_AUTH_METHODS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
        </div>
        <FormField label="Description">
          {(fieldProps) => <Input {...fieldProps} value={description} onChange={(event) => setDescription(event.target.value)} />}
        </FormField>
        <Button type="submit" loading={createConnector.isPending} disabled={!name || !connectorType} className="w-fit">
          Register connector
        </Button>
      </form>
    </Dialog>
  );
}
