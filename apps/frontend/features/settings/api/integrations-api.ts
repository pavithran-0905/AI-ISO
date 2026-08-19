/**
 * `services/integration-hub-service` — a generic connector framework
 * (register/configure/test/enable/disable/remove any third-party
 * system), not a set of named integrations. No dedicated
 * Ansible/Redfish/Kubernetes category or form exists — see the
 * developer guide's "Why no specialized Ansible/Kubernetes form".
 * Deliberately scoped to the core lifecycle this feature builds
 * against: create/list/detail/configure/test/enable/disable/remove
 * plus credential assign/rotate. Versions/upgrade/rollback/deprecate/
 * sync/probe/health-history/marketplace/transformations/flows/events/
 * analytics are all real but out of scope for a Settings page — see
 * the developer guide.
 */

import { apiClient } from "@/api/client";
import type {
  AssignCredentialInput,
  ConfigureConnectorInput,
  ConnectionTestResult,
  Connector,
  ConnectorCredential,
  CreateConnectorInput,
} from "@/features/settings/types";

interface ConnectorResponseBody {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  category: string;
  connector_type: string;
  status: string;
  auth_method: string;
  config: Record<string, unknown>;
  owner_id: string | null;
  enabled: boolean;
  consecutive_failures: number;
  last_validated_at: string | null;
  last_health_check_at: string | null;
  last_sync_at: string | null;
  tags: string[];
  created_at: string;
}

function toConnector(body: ConnectorResponseBody): Connector {
  return {
    id: body.id,
    organizationId: body.organization_id,
    name: body.name,
    description: body.description,
    category: body.category as Connector["category"],
    connectorType: body.connector_type,
    status: body.status as Connector["status"],
    authMethod: body.auth_method as Connector["authMethod"],
    config: body.config,
    ownerId: body.owner_id,
    enabled: body.enabled,
    consecutiveFailures: body.consecutive_failures,
    lastValidatedAt: body.last_validated_at,
    lastHealthCheckAt: body.last_health_check_at,
    lastSyncAt: body.last_sync_at,
    tags: body.tags,
    createdAt: body.created_at,
  };
}

interface ConnectionTestResponseBody {
  id: string;
  connector_id: string;
  credential_id: string | null;
  status: string;
  tested_at: string;
  latency_ms: number | null;
  error: string | null;
  attempt_number: number;
}

interface CredentialResponseBody {
  id: string;
  connector_id: string;
  credential_type: string;
  status: string;
  secret_ref: string | null;
  expires_at: string | null;
  last_validated_at: string | null;
  last_rotated_at: string | null;
  created_at: string;
}

function toCredential(body: CredentialResponseBody): ConnectorCredential {
  return {
    id: body.id,
    connectorId: body.connector_id,
    credentialType: body.credential_type,
    status: body.status,
    secretRef: body.secret_ref,
    expiresAt: body.expires_at,
    lastValidatedAt: body.last_validated_at,
    lastRotatedAt: body.last_rotated_at,
    createdAt: body.created_at,
  };
}

export const integrationsApi = {
  async list(organizationId: string): Promise<Connector[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<ConnectorResponseBody[]>(`/integrations/connectors?${query.toString()}`);
    return body.map(toConnector);
  },

  async getById(connectorId: string): Promise<Connector> {
    const body = await apiClient.get<ConnectorResponseBody>(`/integrations/connectors/${connectorId}`);
    return toConnector(body);
  },

  async create(input: CreateConnectorInput): Promise<Connector> {
    const body = await apiClient.post<ConnectorResponseBody>("/integrations/connectors", {
      organization_id: input.organizationId,
      name: input.name,
      category: input.category,
      connector_type: input.connectorType,
      auth_method: input.authMethod,
      description: input.description,
      tags: input.tags,
    });
    return toConnector(body);
  },

  /** `PUT` — a full replace of the whole `config` dict (confirmed: no
   * `PATCH` exists for this route). Moves the connector to
   * `configured`. */
  async configure(connectorId: string, input: ConfigureConnectorInput): Promise<Connector> {
    const body = await apiClient.put<ConnectorResponseBody>(`/integrations/connectors/${connectorId}`, {
      config: input.config,
    });
    return toConnector(body);
  },

  /** Soft — sets `status` to `removed` and `enabled` to `false`, never
   * deletes the row (confirmed). */
  async remove(connectorId: string): Promise<void> {
    await apiClient.delete(`/integrations/connectors/${connectorId}`);
  },

  /** Makes a real outbound HTTP/TCP check when `config.endpoint_url`
   * or `config.host`+`config.port` are set; otherwise falls back to a
   * structural check (config+credential presence only, no network
   * call) — see `ConnectionTestResult`'s own docstring. On success,
   * the backend also stamps `last_validated_at`. */
  async testConnection(connectorId: string): Promise<ConnectionTestResult> {
    const body = await apiClient.post<ConnectionTestResponseBody>(`/integrations/connectors/${connectorId}/test`);
    return {
      id: body.id,
      connectorId: body.connector_id,
      credentialId: body.credential_id,
      status: body.status as ConnectionTestResult["status"],
      testedAt: body.tested_at,
      latencyMs: body.latency_ms,
      error: body.error,
      attemptNumber: body.attempt_number,
    };
  },

  async enable(connectorId: string): Promise<Connector> {
    const body = await apiClient.post<ConnectorResponseBody>(`/integrations/connectors/${connectorId}/enable`);
    return toConnector(body);
  },

  async disable(connectorId: string): Promise<Connector> {
    const body = await apiClient.post<ConnectorResponseBody>(`/integrations/connectors/${connectorId}/disable`);
    return toConnector(body);
  },

  /** No secret value is ever returned by this route (confirmed absent
   * from the response schema, not even masked) — only a `secretRef`
   * pointer into an external secrets manager. */
  async assignCredential(input: AssignCredentialInput): Promise<ConnectorCredential> {
    const body = await apiClient.post<CredentialResponseBody>("/integrations/credentials", {
      connector_id: input.connectorId,
      credential_type: input.credentialType,
      secret_ref: input.secretRef,
      raw_value: input.rawValue,
      refresh_value: input.refreshValue,
      expires_at: input.expiresAt,
    });
    return toCredential(body);
  },

  async rotateCredential(
    credentialId: string,
    input: { rawValue: string; refreshValue?: string; expiresAt?: string },
  ): Promise<ConnectorCredential> {
    const body = await apiClient.post<CredentialResponseBody>(`/integrations/credentials/${credentialId}/rotate`, {
      raw_value: input.rawValue,
      refresh_value: input.refreshValue,
      expires_at: input.expiresAt,
    });
    return toCredential(body);
  },
};
