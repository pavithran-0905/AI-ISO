/**
 * `services/alerting-service/app/api/alerts.py` — confirmed by source
 * inspection. `GET /alerts` supports only `organization_id` (required),
 * `status`, `severity` — no pagination, search, or sort exist on this
 * endpoint (confirmed by reading the full route signature and the
 * `list_for_org` service method it calls). See
 * `docs/frontend/developer-guide/alerting.md` for what this means for
 * the frontend's own client-side search/sort.
 */

import { apiClient } from "@/api/client";
import type {
  Alert,
  AlertAcknowledgement,
  AlertCorrelation,
  AlertHistoryEntry,
  AlertListParams,
  AlertNotification,
  AlertSeverity,
  AlertStatusValue,
  AlertUpdateInput,
} from "@/features/alerting/types";

interface AlertResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  rule_id: string | null;
  source: string;
  severity: AlertSeverity;
  status: AlertStatusValue;
  title: string;
  message: string;
  fingerprint: string;
  source_reference: Record<string, unknown>;
  assigned_to: string | null;
  triggered_at: string;
  resolved_at: string | null;
  closed_at: string | null;
}

interface AlertHistoryResponseBody {
  id: string;
  alert_id: string;
  from_status: AlertStatusValue | null;
  to_status: AlertStatusValue;
  changed_by: string | null;
  reason: string | null;
  changed_at: string;
}

interface AlertAcknowledgementResponseBody {
  id: string;
  alert_id: string;
  acknowledgement_type: string;
  acknowledged_by: string | null;
  comment: string | null;
  resolution_notes: string | null;
  acknowledged_at: string;
}

interface AlertCorrelationResponseBody {
  id: string;
  parent_alert_id: string;
  child_alert_id: string;
  correlation_type: string;
  correlated_at: string;
}

interface AlertNotificationResponseBody {
  id: string;
  alert_id: string;
  route_id: string | null;
  channel: string;
  status: string;
  retry_count: number;
  error_message: string | null;
  sent_at: string | null;
}

function toAlert(body: AlertResponseBody): Alert {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    ruleId: body.rule_id,
    source: body.source,
    severity: body.severity,
    status: body.status,
    title: body.title,
    message: body.message,
    fingerprint: body.fingerprint,
    sourceReference: body.source_reference,
    assignedTo: body.assigned_to,
    triggeredAt: body.triggered_at,
    resolvedAt: body.resolved_at,
    closedAt: body.closed_at,
  };
}

function toHistoryEntry(body: AlertHistoryResponseBody): AlertHistoryEntry {
  return {
    id: body.id,
    alertId: body.alert_id,
    fromStatus: body.from_status,
    toStatus: body.to_status,
    changedBy: body.changed_by,
    reason: body.reason,
    changedAt: body.changed_at,
  };
}

function toAcknowledgement(body: AlertAcknowledgementResponseBody): AlertAcknowledgement {
  return {
    id: body.id,
    alertId: body.alert_id,
    acknowledgementType: body.acknowledgement_type,
    acknowledgedBy: body.acknowledged_by,
    comment: body.comment,
    resolutionNotes: body.resolution_notes,
    acknowledgedAt: body.acknowledged_at,
  };
}

function toCorrelation(body: AlertCorrelationResponseBody): AlertCorrelation {
  return {
    id: body.id,
    parentAlertId: body.parent_alert_id,
    childAlertId: body.child_alert_id,
    correlationType: body.correlation_type,
    correlatedAt: body.correlated_at,
  };
}

function toNotification(body: AlertNotificationResponseBody): AlertNotification {
  return {
    id: body.id,
    alertId: body.alert_id,
    routeId: body.route_id,
    channel: body.channel,
    status: body.status,
    retryCount: body.retry_count,
    errorMessage: body.error_message,
    sentAt: body.sent_at,
  };
}

function buildListQuery(params: AlertListParams): string {
  const query = new URLSearchParams({ organization_id: params.organizationId });
  if (params.status) query.set("status", params.status);
  if (params.severity) query.set("severity", params.severity);
  return query.toString();
}

export const alertsApi = {
  async list(params: AlertListParams): Promise<Alert[]> {
    const body = await apiClient.get<AlertResponseBody[]>(`/alerts?${buildListQuery(params)}`);
    return body.map(toAlert);
  },

  async getById(id: string): Promise<Alert> {
    const body = await apiClient.get<AlertResponseBody>(`/alerts/${encodeURIComponent(id)}`);
    return toAlert(body);
  },

  async update(id: string, input: AlertUpdateInput): Promise<Alert> {
    const body = await apiClient.put<AlertResponseBody>(`/alerts/${encodeURIComponent(id)}`, {
      severity: input.severity,
      title: input.title,
      message: input.message,
      assigned_to: input.assignedTo,
    });
    return toAlert(body);
  },

  /** `DELETE /alerts/{id}` is a status transition to `closed`, not a
   * row deletion — confirmed by source inspection of the route's own
   * docstring. */
  async close(id: string): Promise<Alert> {
    const body = await apiClient.delete<AlertResponseBody>(`/alerts/${encodeURIComponent(id)}`);
    return toAlert(body);
  },

  async acknowledge(id: string, comment?: string): Promise<Alert> {
    const body = await apiClient.post<AlertResponseBody>(`/alerts/${encodeURIComponent(id)}/acknowledge`, { comment });
    return toAlert(body);
  },

  async resolve(id: string, resolutionNotes?: string): Promise<Alert> {
    const body = await apiClient.post<AlertResponseBody>(`/alerts/${encodeURIComponent(id)}/resolve`, {
      resolution_notes: resolutionNotes,
    });
    return toAlert(body);
  },

  async escalate(id: string, options?: { policyId?: string; reason?: string }): Promise<Alert> {
    const body = await apiClient.post<AlertResponseBody>(`/alerts/${encodeURIComponent(id)}/escalate`, {
      policy_id: options?.policyId,
      reason: options?.reason,
    });
    return toAlert(body);
  },

  async listHistory(id: string): Promise<AlertHistoryEntry[]> {
    const body = await apiClient.get<AlertHistoryResponseBody[]>(`/alerts/${encodeURIComponent(id)}/history`);
    return body.map(toHistoryEntry);
  },

  async listAcknowledgements(id: string): Promise<AlertAcknowledgement[]> {
    const body = await apiClient.get<AlertAcknowledgementResponseBody[]>(
      `/alerts/${encodeURIComponent(id)}/acknowledgements`,
    );
    return body.map(toAcknowledgement);
  },

  async listCorrelations(id: string): Promise<AlertCorrelation[]> {
    const body = await apiClient.get<AlertCorrelationResponseBody[]>(`/alerts/${encodeURIComponent(id)}/correlations`);
    return body.map(toCorrelation);
  },

  async listNotifications(id: string): Promise<AlertNotification[]> {
    const body = await apiClient.get<AlertNotificationResponseBody[]>(`/alerts/${encodeURIComponent(id)}/notifications`);
    return body.map(toNotification);
  },
};
