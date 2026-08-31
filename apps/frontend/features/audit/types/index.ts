/**
 * Types mirroring real V1 responses this feature consumes, confirmed
 * by direct source inspection across ten services. **There is no
 * platform-wide audit log anywhere in this backend** — only three
 * services expose a real, general-purpose, `AuditAction`-typed audit
 * route (`compliance-service`, `integration-hub-service`,
 * `notification-center-service`), and each records only actions taken
 * through its own API. Six other services (`authentication-service`,
 * `rbac-service`, `administration-portal-service`, `automation-service`,
 * `inventory-service`, `observability-platform-service`) have a real,
 * populated audit table with zero route reaching it. See
 * `docs/frontend/developer-guide/audit-activity.md` for the full
 * per-service breakdown.
 */

/** The three real, independently-fetched audit sources this feature
 * aggregates through one shared UI — never silently merged into one
 * combined list, since that would mean fabricating a single "page N
 * of M" that doesn't correspond to any real backend query. */
export const AUDIT_SOURCES = ["compliance", "integrations", "notifications"] as const;
export type AuditSourceValue = (typeof AUDIT_SOURCES)[number];

export const AUDIT_SOURCE_LABELS: Record<AuditSourceValue, string> = {
  compliance: "Compliance",
  integrations: "Integrations",
  notifications: "Notifications",
};

/** Each source's real, complete `AuditAction` enum — confirmed by
 * source inspection of each service's own `app/models/enums.py`. Used
 * only for `notifications`' real action filter (§16: "Use backend-
 * supported values. Do not hardcode speculative event types.");
 * `compliance` and `integrations` have no action filter on their audit
 * routes, so these two lists are display-reference only. */
export const COMPLIANCE_AUDIT_ACTIONS = [
  "framework_created", "framework_updated", "control_created", "control_updated", "control_mapped",
  "assessment_created", "assessment_completed", "scan_started", "evidence_collected", "finding_raised",
  "finding_updated", "exception_requested", "exception_approved", "exception_revoked", "risk_registered",
  "risk_updated", "remediation_created", "remediation_verified", "report_generated", "administrative",
] as const;

export const INTEGRATIONS_AUDIT_ACTIONS = [
  "connector_registered", "connector_configured", "connector_enabled", "connector_disabled",
  "connector_upgraded", "connector_rolled_back", "connector_removed", "credential_assigned",
  "credential_rotated", "sync_triggered", "flow_executed", "marketplace_published", "administrative",
] as const;

export const NOTIFICATIONS_AUDIT_ACTIONS = [
  "notification_created", "notification_sent", "notification_cancelled", "template_created",
  "template_updated", "preference_updated", "subscription_created", "subscription_removed",
  "announcement_published", "announcement_updated", "broadcast_initiated", "channel_configured",
  "report_generated", "administrative",
] as const;

/**
 * A unified frontend shape over three near-identical, but not
 * identical, real `AuditEntryResponse`/`AuditResponse` schemas.
 * `context` is `null` for `compliance` events — confirmed absent from
 * that service's own response schema (the model has it, the API
 * doesn't expose it) — never fabricated to look present.
 */
export interface AuditEvent {
  id: string;
  source: AuditSourceValue;
  action: string;
  entityType: string;
  entityId: string | null;
  entityReference: string | null;
  actorId: string | null;
  actorType: string;
  occurredAt: string;
  summary: string;
  succeeded: boolean;
  changes: Record<string, unknown>;
  context: Record<string, unknown> | null;
}

/**
 * Real filters, but genuinely different per source — never offered
 * as if universal. `compliance`: entityType/entityId/actorId/days
 * (relative window, max 3650, no absolute end date)/limit/offset, no
 * action filter. `integrations`: organizationId/limit/offset only —
 * confirmed no action/entity/actor filter on the route despite the
 * service supporting them internally. `notifications`: the richest —
 * organizationId/action/entityId/actorId/limit/offset. None of the
 * three exposes a status/succeeded filter or a client-controlled sort
 * field (all fixed `occurred_at desc`).
 */
export interface AuditEventSearchParams {
  organizationId: string;
  entityType?: string;
  entityId?: string;
  actorId?: string;
  action?: string;
  days?: number;
  limit?: number;
  offset?: number;
}

export interface AuditEventSearchResult {
  items: AuditEvent[];
  offset: number;
  limit: number;
  hasMore: boolean;
}

/** `GET /compliance/audit/summary` and `GET /notifications/audit/summary`
 * — both real, same shape. `integration-hub-service` has no summary
 * route (confirmed absent) — its Overview card shows a real recent-
 * count from the plain list call instead, documented as such. */
export interface AuditSummary {
  since: string;
  total: number;
  byAction: Record<string, number>;
}

export const FINDING_SEVERITIES = ["critical", "high", "medium", "low", "informational"] as const;
export type FindingSeverityValue = (typeof FINDING_SEVERITIES)[number];

/** `GET /compliance/findings/summary` — real, cheap compliance-posture
 * signal shown on the Overview. Full findings/frameworks/controls/
 * risk-register/remediation management is real but deliberately out
 * of scope for this prompt's own IA (Overview/Activity/Audit Events/
 * Event Detail only) — see the developer guide. Field names mirror
 * `FindingService.summary()` exactly, confirmed by source inspection
 * (`services/compliance-service/app/services/finding.py:329`). */
export interface FindingsSummary {
  openTotal: number;
  bySeverity: Record<string, number>;
  criticalOpen: number;
  overdue: number;
  openStatuses: string[];
}

/**
 * Export is real, but only for `compliance` — `POST /compliance/reports
 * {kind:"audit"}` → `GET /compliance/reports/{id}/download`
 * (`services/compliance-service/app/services/reporting.py:251-316,542-560`,
 * confirmed synchronous: the POST itself returns the finished report,
 * never a job handle to poll). `integrations`/`notifications` have no
 * export or report-generation route of any kind — no export control is
 * shown for those sources. This pipeline belongs to compliance-service
 * alone; it has no technical relationship to Prompt 008's
 * `reporting-service` Reporting feature despite both being called
 * "reports" — the prompt's suggested "Audit → Reporting" integration
 * does not correspond to anything V1 actually connects, so this
 * feature does not link to `/reporting` for audit export. The exported
 * row shape is narrower than the live `/compliance/audit` response —
 * confirmed by reading `_audit()`: no `id`, `entity_id`, `actor_type`,
 * `changes`, or `context`, only `occurred_at, action, entity_type,
 * entity_reference, actor, summary, succeeded`.
 */
export const AUDIT_REPORT_FORMATS = ["json", "csv", "markdown"] as const;
export type AuditReportFormatValue = (typeof AUDIT_REPORT_FORMATS)[number];

export interface AuditReportRequest {
  organizationId: string;
  reportFormat: AuditReportFormatValue;
  periodDays: number;
}

export interface AuditReportResult {
  id: string;
  status: string;
  error: string | null;
}
