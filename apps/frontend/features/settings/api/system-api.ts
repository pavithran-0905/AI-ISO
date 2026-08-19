/**
 * `services/administration-portal-service` — platform-wide settings,
 * feature flags, background jobs, and read-only observability.
 * `organization_id` is always derived from the JWT claim server-side,
 * never a client-supplied param (confirmed) — unlike every other
 * service this session, there is no cross-tenant read risk here from
 * a caller-supplied id.
 *
 * **Permission note**: mutations require one of `admin`/`administrator`/
 * `platform_admin`/`super_admin` in the JWT's `roles` *array* claim
 * (confirmed, enforced, tested) — a different claim shape from the
 * rest of this platform's own `role` (singular) claim, which itself is
 * not populated at login today (the documented Prompt 001 gap). Net
 * effect: every mutation below will 403 for every current session,
 * regardless of the frontend's own coarse role gating — see the
 * developer guide. Reads require only a valid JWT, no role check.
 * Tenant management (`/admin/tenants*`) is deliberately not built
 * against here — real, but cross-organization operator tooling, not a
 * per-organization Settings page concern (see the developer guide).
 */

import { apiClient } from "@/api/client";
import type {
  AdminDashboardSnapshot,
  AdminReportMeta,
  CreateFeatureFlagInput,
  DiagnosticEntry,
  EnqueueSystemJobInput,
  FeatureFlag,
  PlatformHealth,
  PlatformSetting,
  StatisticWindow,
  SystemJob,
  UpdateFeatureFlagInput,
  UpsertPlatformSettingInput,
} from "@/features/settings/types";

interface DashboardResponseBody {
  tenant_count: number;
  active_tenant_count: number;
  organization_count: number;
  running_job_count: number;
  failed_job_count: number;
  open_maintenance_window_count: number;
  overall_health: string;
}

interface SettingResponseBody {
  id: string;
  key: string;
  value: unknown;
  description: string | null;
}

function toSetting(body: SettingResponseBody): PlatformSetting {
  return { id: body.id, key: body.key, value: body.value, description: body.description };
}

interface FeatureFlagResponseBody {
  id: string;
  name: string;
  scope: string;
  target_ref: string | null;
  rollout_percentage: number;
  is_enabled: boolean;
  is_killed: boolean;
}

function toFeatureFlag(body: FeatureFlagResponseBody): FeatureFlag {
  return {
    id: body.id,
    name: body.name,
    scope: body.scope,
    targetRef: body.target_ref,
    rolloutPercentage: body.rollout_percentage,
    isEnabled: body.is_enabled,
    isKilled: body.is_killed,
  };
}

interface JobResponseBody {
  id: string;
  job_key: string;
  status: string;
  priority: string;
  attempt_count: number;
  max_attempts: number;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
}

function toJob(body: JobResponseBody): SystemJob {
  return {
    id: body.id,
    jobKey: body.job_key,
    status: body.status,
    priority: body.priority,
    attemptCount: body.attempt_count,
    maxAttempts: body.max_attempts,
    queuedAt: body.queued_at,
    startedAt: body.started_at,
    completedAt: body.completed_at,
  };
}

const LIMIT = 100;

export const systemApi = {
  async getDashboard(): Promise<AdminDashboardSnapshot> {
    const body = await apiClient.get<DashboardResponseBody>("/admin/dashboard");
    return {
      tenantCount: body.tenant_count,
      activeTenantCount: body.active_tenant_count,
      organizationCount: body.organization_count,
      runningJobCount: body.running_job_count,
      failedJobCount: body.failed_job_count,
      openMaintenanceWindowCount: body.open_maintenance_window_count,
      overallHealth: body.overall_health,
    };
  },

  async listSettings(): Promise<PlatformSetting[]> {
    const body = await apiClient.get<{ settings: SettingResponseBody[]; total: number }>("/admin/settings");
    return body.settings.map(toSetting);
  },

  /** Admin-role-gated upsert-by-key. */
  async upsertSetting(input: UpsertPlatformSettingInput): Promise<PlatformSetting> {
    const body = await apiClient.put<SettingResponseBody>("/admin/settings", {
      key: input.key,
      value: input.value,
      description: input.description,
    });
    return toSetting(body);
  },

  async listFeatureFlags(): Promise<FeatureFlag[]> {
    const body = await apiClient.get<{ feature_flags: FeatureFlagResponseBody[]; total: number }>(
      `/admin/feature-flags?limit=${LIMIT}`,
    );
    return body.feature_flags.map(toFeatureFlag);
  },

  async createFeatureFlag(input: CreateFeatureFlagInput): Promise<FeatureFlag> {
    const body = await apiClient.post<FeatureFlagResponseBody>("/admin/feature-flags", {
      name: input.name,
      scope: input.scope,
      target_ref: input.targetRef,
      rollout_percentage: input.rolloutPercentage,
    });
    return toFeatureFlag(body);
  },

  /** Genuinely partial — every field on this request is optional. */
  async updateFeatureFlag(flagId: string, input: UpdateFeatureFlagInput): Promise<FeatureFlag> {
    const body = await apiClient.put<FeatureFlagResponseBody>(`/admin/feature-flags/${flagId}`, {
      is_enabled: input.isEnabled,
      is_killed: input.isKilled,
      rollout_percentage: input.rolloutPercentage,
    });
    return toFeatureFlag(body);
  },

  async listJobs(): Promise<SystemJob[]> {
    const body = await apiClient.get<{ jobs: JobResponseBody[]; total: number }>(`/admin/jobs?limit=${LIMIT}`);
    return body.jobs.map(toJob);
  },

  /** No route cancels, retries, or otherwise transitions a job after
   * enqueue (confirmed absent) — this is the only mutation available. */
  async enqueueJob(input: EnqueueSystemJobInput): Promise<SystemJob> {
    const body = await apiClient.post<JobResponseBody>("/admin/jobs", {
      job_key: input.jobKey,
      priority: input.priority,
      payload: input.payload,
      max_attempts: input.maxAttempts,
    });
    return toJob(body);
  },

  async listDiagnostics(): Promise<DiagnosticEntry[]> {
    const body = await apiClient.get<{ diagnostics: { id: string; category: string; status: string; latency_ms: number | null; ran_at: string }[]; total: number }>(
      `/admin/diagnostics?limit=${LIMIT}`,
    );
    return body.diagnostics.map((entry) => ({
      id: entry.id,
      category: entry.category,
      status: entry.status,
      latencyMs: entry.latency_ms,
      ranAt: entry.ran_at,
    }));
  },

  async getHealth(): Promise<PlatformHealth> {
    const body = await apiClient.get<{
      overall_status: string;
      components: { component: string; status: string; checked_at: string }[];
    }>("/admin/health");
    return {
      overallStatus: body.overall_status,
      components: body.components.map((component) => ({
        component: component.component,
        status: component.status,
        checkedAt: component.checked_at,
      })),
    };
  },

  async getStatistics(): Promise<StatisticWindow[]> {
    const body = await apiClient.get<{
      windows: {
        window_start: string;
        window_end: string;
        tenant_count: number;
        user_count: number;
        api_request_count: number;
        background_job_count: number;
        security_event_count: number;
        platform_availability_fraction: number;
      }[];
      total: number;
    }>("/admin/statistics");
    return body.windows.map((window) => ({
      windowStart: window.window_start,
      windowEnd: window.window_end,
      tenantCount: window.tenant_count,
      userCount: window.user_count,
      apiRequestCount: window.api_request_count,
      backgroundJobCount: window.background_job_count,
      securityEventCount: window.security_event_count,
      platformAvailabilityFraction: window.platform_availability_fraction,
    }));
  },

  /** Metadata only — no report content/download field exists on this
   * response (confirmed absent). */
  async listReports(): Promise<AdminReportMeta[]> {
    const body = await apiClient.get<{
      reports: {
        id: string;
        kind: string;
        report_format: string;
        title: string;
        status: string;
        period_start: string;
        period_end: string;
        generated_at: string | null;
        row_count: number | null;
      }[];
      total: number;
    }>(`/admin/reports?limit=${LIMIT}`);
    return body.reports.map((report) => ({
      id: report.id,
      kind: report.kind,
      reportFormat: report.report_format,
      title: report.title,
      status: report.status,
      periodStart: report.period_start,
      periodEnd: report.period_end,
      generatedAt: report.generated_at,
      rowCount: report.row_count,
    }));
  },
};
