/**
 * Types mirroring the real V1 responses this dashboard consumes,
 * confirmed by direct source inspection — never inferred from a
 * service's name. See `docs/frontend/developer-guide/dashboard.md` for
 * the endpoint each one comes from.
 */

export const ALERT_SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
export type AlertSeverity = (typeof ALERT_SEVERITIES)[number];

/** `AlertStatus` per `services/alerting-service/app/models/enums.py` —
 * the full set the backend can report. `RESOLVED_STATUSES` below is
 * this dashboard's own (documented, not backend-defined) notion of
 * "no longer needs attention." */
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

export const RESOLVED_ALERT_STATUSES: ReadonlySet<AlertStatusValue> = new Set(["resolved", "closed", "expired"]);

export interface Alert {
  id: string;
  organizationId: string;
  severity: AlertSeverity;
  status: AlertStatusValue;
  title: string;
  message: string;
  source: string;
  triggeredAt: string;
  resolvedAt: string | null;
}

/** `ExecutionStatus` per `services/automation-service/app/models/enums.py`. */
export const EXECUTION_STATUSES = [
  "pending",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
  "timed_out",
  "rolled_back",
] as const;
export type ExecutionStatusValue = (typeof EXECUTION_STATUSES)[number];

export interface AutomationExecution {
  id: string;
  organizationId: string;
  jobId: string;
  status: ExecutionStatusValue;
  triggeredBy: string | null;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
}

/** `HealthState` per `services/api-gateway-service/app/models/enums.py`
 * (mirrors `shared_core.enums.health_status.HealthStatus`). */
export const HEALTH_STATES = ["healthy", "degraded", "warning", "unhealthy", "maintenance", "unknown"] as const;
export type HealthStateValue = (typeof HEALTH_STATES)[number];

/** `ServiceHealthResponse` per `services/api-gateway-service/app/schemas/gateway.py`. */
export interface ServiceHealthInstance {
  serviceId: string;
  instanceUrl: string;
  status: HealthStateValue;
  latencyMs: number | null;
  error: string | null;
  checkedAt: string;
}

export interface AggregatedGatewayHealth {
  overallStatus: HealthStateValue;
  instances: ServiceHealthInstance[];
}
