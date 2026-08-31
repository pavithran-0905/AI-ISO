/**
 * Three real, separately-scoped audit endpoints:
 * `GET /compliance/audit`(+`/summary`), `GET /integrations/audit`,
 * `GET /notifications/audit`(+`/summary`). No route on any of the
 * three services returns a single event by its own id — "detail" is
 * built entirely from the already-loaded list row, never a second
 * fetch (see `features/audit/components/event-detail-drawer.tsx`).
 * None of the three enforces a role/permission check beyond (at most)
 * a valid JWT — `integrations`/`notifications` don't even require a
 * JWT on these specific routes (confirmed: `CurrentUserId` isn't a
 * declared parameter on either). This module still always sends the
 * real, currently-selected organization on every call, the same
 * discipline every other tenant-isolation gap this session found.
 */

import { apiClient } from "@/api/client";
import { fetchBinary, saveBlob, type BinaryDownload } from "@/features/audit/lib/binary-fetch";
import type {
  AuditEvent,
  AuditEventSearchParams,
  AuditEventSearchResult,
  AuditReportRequest,
  AuditReportResult,
  AuditSourceValue,
  AuditSummary,
  FindingsSummary,
} from "@/features/audit/types";

interface AuditEntryBody {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  entity_reference: string | null;
  actor_id: string | null;
  actor_type: string;
  occurred_at: string;
  summary: string;
  succeeded: boolean;
  changes: Record<string, unknown>;
  context?: Record<string, unknown>;
}

function toEvent(body: AuditEntryBody, source: AuditSourceValue): AuditEvent {
  return {
    id: body.id,
    source,
    action: body.action,
    entityType: body.entity_type,
    entityId: body.entity_id,
    entityReference: body.entity_reference,
    actorId: body.actor_id,
    actorType: body.actor_type,
    occurredAt: body.occurred_at,
    summary: body.summary,
    succeeded: body.succeeded,
    changes: body.changes,
    context: body.context ?? null,
  };
}

const DEFAULT_LIMIT = 50;

export const auditApi = {
  /** `GET /compliance/audit` — `days` is a relative window (default
   * 90, max 3650), not an absolute start/end date-range pair; no
   * `action` filter exists on this route. */
  async searchCompliance(params: AuditEventSearchParams): Promise<AuditEventSearchResult> {
    const limit = params.limit ?? DEFAULT_LIMIT;
    const offset = params.offset ?? 0;
    const query = new URLSearchParams({ organization_id: params.organizationId, limit: String(limit), offset: String(offset) });
    if (params.entityType) query.set("entity_type", params.entityType);
    if (params.entityId) query.set("entity_id", params.entityId);
    if (params.actorId) query.set("actor_id", params.actorId);
    if (params.days) query.set("days", String(params.days));
    const body = await apiClient.get<AuditEntryBody[]>(`/compliance/audit?${query.toString()}`);
    return { items: body.map((entry) => toEvent(entry, "compliance")), offset, limit, hasMore: body.length === limit };
  },

  async getComplianceSummary(organizationId: string, days = 30): Promise<AuditSummary> {
    const query = new URLSearchParams({ organization_id: organizationId, days: String(days) });
    const body = await apiClient.get<{ since: string; total: number; by_action: Record<string, number> }>(`/compliance/audit/summary?${query.toString()}`);
    return { since: body.since, total: body.total, byAction: body.by_action };
  },

  async getFindingsSummary(organizationId: string): Promise<FindingsSummary> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<{
      open_total: number;
      by_severity: Record<string, number>;
      critical_open: number;
      overdue: number;
      open_statuses: string[];
    }>(`/compliance/findings/summary?${query.toString()}`);
    return { openTotal: body.open_total, bySeverity: body.by_severity, criticalOpen: body.critical_open, overdue: body.overdue, openStatuses: body.open_statuses };
  },

  /** `GET /integrations/audit` — confirmed no `action`/`entity_id`/
   * `actor_id` filter exists on this specific route (the service
   * supports them internally; the route just never wires them in) —
   * those params are silently ignored here rather than sent and
   * pretending they work. No `/summary` route exists on this service. */
  async searchIntegrations(params: AuditEventSearchParams): Promise<AuditEventSearchResult> {
    const limit = params.limit ?? DEFAULT_LIMIT;
    const offset = params.offset ?? 0;
    const query = new URLSearchParams({ organization_id: params.organizationId, limit: String(limit), offset: String(offset) });
    const body = await apiClient.get<AuditEntryBody[]>(`/integrations/audit?${query.toString()}`);
    return { items: body.map((entry) => toEvent(entry, "integrations")), offset, limit, hasMore: body.length === limit };
  },

  /** `GET /notifications/audit` — the richest filter set of the
   * three: real `action`/`entity_id`/`actor_id` support. */
  async searchNotifications(params: AuditEventSearchParams): Promise<AuditEventSearchResult> {
    const limit = params.limit ?? DEFAULT_LIMIT;
    const offset = params.offset ?? 0;
    const query = new URLSearchParams({ organization_id: params.organizationId, limit: String(limit), offset: String(offset) });
    if (params.action) query.set("action", params.action);
    if (params.entityId) query.set("entity_id", params.entityId);
    if (params.actorId) query.set("actor_id", params.actorId);
    const body = await apiClient.get<AuditEntryBody[]>(`/notifications/audit?${query.toString()}`);
    return { items: body.map((entry) => toEvent(entry, "notifications")), offset, limit, hasMore: body.length === limit };
  },

  async getNotificationsSummary(organizationId: string, days = 30): Promise<AuditSummary> {
    const query = new URLSearchParams({ organization_id: organizationId, days: String(days) });
    const body = await apiClient.get<{ since: string; total: number; by_action: Record<string, number> }>(`/notifications/audit/summary?${query.toString()}`);
    return { since: body.since, total: body.total, byAction: body.by_action };
  },

  async search(source: AuditSourceValue, params: AuditEventSearchParams): Promise<AuditEventSearchResult> {
    if (source === "compliance") return auditApi.searchCompliance(params);
    if (source === "integrations") return auditApi.searchIntegrations(params);
    return auditApi.searchNotifications(params);
  },

  /** `POST /compliance/reports {kind:"audit"}` — synchronous; the
   * response already carries a terminal `status` (`completed`/`failed`),
   * never a job id to poll. `compliance` source only — see the
   * `AuditReportRequest` docstring for why this isn't offered for the
   * other two sources or bridged through Reporting. */
  async generateAuditReport(params: AuditReportRequest): Promise<AuditReportResult> {
    const query = new URLSearchParams({ organization_id: params.organizationId });
    const body = await apiClient.post<{ id: string; status: string; error: string | null }>(`/compliance/reports?${query.toString()}`, {
      kind: "audit",
      report_format: params.reportFormat,
      period_days: params.periodDays,
    });
    return { id: body.id, status: body.status, error: body.error };
  },

  async downloadAuditReport(organizationId: string, reportId: string, fallbackFilename: string): Promise<BinaryDownload> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const download = await fetchBinary(`/compliance/reports/${reportId}/download?${query.toString()}`, fallbackFilename);
    saveBlob(download);
    return download;
  },
};
