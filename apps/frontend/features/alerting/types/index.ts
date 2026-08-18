/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection of `services/alerting-service`
 * — never inferred from a service's name. See
 * `docs/frontend/developer-guide/alerting.md` for the endpoint each
 * one comes from.
 *
 * This is the canonical home for alert data — `features/dashboard`
 * (Prompt 005) originally had its own copy of `Alert`/`AlertSeverity`/
 * `AlertStatusValue`, consolidated in here (Prompt 006) so the
 * Dashboard's "Attention Required" section and this feature share one
 * fetch path (§24: "do not duplicate alert-fetching logic inside
 * Dashboard").
 */

export const ALERT_SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
export type AlertSeverity = (typeof ALERT_SEVERITIES)[number];

/** `AlertStatus` — `services/alerting-service/app/models/enums.py`. */
export const ALERT_STATUSES = [
  "new",
  "open",
  "acknowledged",
  "investigating",
  "suppressed",
  "escalated",
  "resolved",
  "closed",
  "expired",
] as const;
export type AlertStatusValue = (typeof ALERT_STATUSES)[number];

/** This feature's own (documented, not backend-defined) notion of "no
 * longer needs attention." */
export const RESOLVED_ALERT_STATUSES: ReadonlySet<AlertStatusValue> = new Set(["resolved", "closed", "expired"]);

export interface Alert {
  id: string;
  organizationId: string;
  projectId: string | null;
  ruleId: string | null;
  source: string;
  severity: AlertSeverity;
  status: AlertStatusValue;
  title: string;
  message: string;
  fingerprint: string;
  /** `AlertResponse.source_reference` is `dict[str, Any]` — free-form,
   * caller-supplied identity data set at ingestion time (`app/services/
   * ingestion.py`), always present (defaults to `{}`), never a single
   * scalar id. No fixed key (e.g. an asset id) is guaranteed to exist
   * in it — see
   * `docs/frontend/backend-v1-integration-limitations.md`. */
  sourceReference: Record<string, unknown>;
  assignedTo: string | null;
  triggeredAt: string;
  resolvedAt: string | null;
  closedAt: string | null;
}

export interface AlertListParams {
  organizationId: string;
  status?: AlertStatusValue;
  severity?: AlertSeverity;
}

export interface AlertUpdateInput {
  severity?: AlertSeverity;
  title?: string;
  message?: string;
  assignedTo?: string;
}

/** `AlertHistoryResponse` — `GET /alerts/{id}/history`, a real
 * per-alert audit trail populated on every status transition. */
export interface AlertHistoryEntry {
  id: string;
  alertId: string;
  fromStatus: AlertStatusValue | null;
  toStatus: AlertStatusValue;
  changedBy: string | null;
  reason: string | null;
  changedAt: string;
}

/** `AlertAcknowledgementResponse` — `GET /alerts/{id}/acknowledgements`.
 * A real, separate table — potentially multiple rows per alert (one per
 * acknowledge/resolve action), not a single field on `Alert` itself. */
export interface AlertAcknowledgement {
  id: string;
  alertId: string;
  /** `"manual" | "automatic"` per the backend enum — kept as `string`
   * since the exact lowercase wire value wasn't independently
   * re-confirmed beyond the Python member names. */
  acknowledgementType: string;
  acknowledgedBy: string | null;
  comment: string | null;
  resolutionNotes: string | null;
  acknowledgedAt: string;
}

/** `AlertCorrelationResponse` — `GET /alerts/{id}/correlations`. Only
 * the children correlated *to* this alert — not a general grouping/
 * cluster endpoint. */
export interface AlertCorrelation {
  id: string;
  parentAlertId: string;
  childAlertId: string;
  correlationType: string;
  correlatedAt: string;
}

/** `AlertNotificationResponse` — `GET /alerts/{id}/notifications`. */
export interface AlertNotification {
  id: string;
  alertId: string;
  routeId: string | null;
  channel: string;
  status: string;
  retryCount: number;
  errorMessage: string | null;
  sentAt: string | null;
}

/** `MaintenanceWindowResponse` — `GET /maintenance-windows`. */
export interface MaintenanceWindow {
  id: string;
  organizationId: string;
  projectId: string | null;
  name: string;
  windowType: string;
  scope: string;
  scopeReference: string | null;
  startsAt: string;
  endsAt: string;
  enabled: boolean;
}

/** `AlertStatisticsResponse` — `GET /alert-statistics`. Only the
 * well-typed scalar fields; `top_sources`/`top_rules`/`trend_data`/
 * `escalation_statistics` are untyped `dict[str, Any]` at the schema
 * level and deliberately not surfaced — see
 * `docs/frontend/backend-v1-integration-limitations.md`. */
export interface AlertStatistics {
  totalAlerts: number;
  openAlertCount: number;
  noiseRatio: number;
  suppressionRate: number;
  averageResolutionSeconds: number | null;
  mttaSeconds: number | null;
  mttrSeconds: number | null;
  computedAt: string;
}
