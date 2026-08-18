/**
 * `services/reporting-service/app/api/delivery.py`'s schedule routes —
 * confirmed by source inspection. There is no dedicated enable/disable
 * endpoint — it's the `enabled` field on `ScheduleUpdateRequest`. `starts_at`
 * cannot be changed once a schedule exists (absent from the update body).
 */

import { apiClient } from "@/api/client";
import type {
  ExportFormat,
  ReportSchedule,
  ScheduleCreateInput,
  ScheduleFrequencyValue,
  ScheduleUpdateInput,
} from "@/features/reporting/types";

interface ScheduleResponseBody {
  id: string;
  job_id: string;
  frequency: ScheduleFrequencyValue;
  cron_expression: string | null;
  timezone: string;
  export_format: ExportFormat;
  starts_at: string;
  ends_at: string | null;
  next_run_at: string | null;
  last_run_at: string | null;
  max_retries: number;
  consecutive_failures: number;
  notify_on_failure: boolean;
  last_error: string | null;
  enabled: boolean;
}

function toSchedule(body: ScheduleResponseBody): ReportSchedule {
  return {
    id: body.id,
    jobId: body.job_id,
    frequency: body.frequency,
    cronExpression: body.cron_expression,
    timezone: body.timezone,
    exportFormat: body.export_format,
    startsAt: body.starts_at,
    endsAt: body.ends_at,
    nextRunAt: body.next_run_at,
    lastRunAt: body.last_run_at,
    maxRetries: body.max_retries,
    consecutiveFailures: body.consecutive_failures,
    notifyOnFailure: body.notify_on_failure,
    lastError: body.last_error,
    enabled: body.enabled,
  };
}

export const schedulesApi = {
  async list(organizationId: string, reportId?: string): Promise<ReportSchedule[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (reportId) query.set("report_id", reportId);
    const body = await apiClient.get<ScheduleResponseBody[]>(`/reports/schedules?${query.toString()}`);
    return body.map(toSchedule);
  },

  async create(input: ScheduleCreateInput): Promise<ReportSchedule> {
    const body = await apiClient.post<ScheduleResponseBody>("/reports/schedule", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      report_id: input.reportId,
      frequency: input.frequency,
      starts_at: input.startsAt,
      ends_at: input.endsAt,
      cron_expression: input.cronExpression,
      timezone: input.timezone,
      export_format: input.exportFormat,
      max_retries: input.maxRetries,
      notify_on_failure: input.notifyOnFailure,
    });
    return toSchedule(body);
  },

  async update(id: string, input: ScheduleUpdateInput): Promise<ReportSchedule> {
    const body = await apiClient.put<ScheduleResponseBody>(`/reports/schedules/${encodeURIComponent(id)}`, {
      frequency: input.frequency,
      cron_expression: input.cronExpression,
      timezone: input.timezone,
      export_format: input.exportFormat,
      ends_at: input.endsAt,
      enabled: input.enabled,
    });
    return toSchedule(body);
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete<null>(`/reports/schedules/${encodeURIComponent(id)}`);
  },
};
