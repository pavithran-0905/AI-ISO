/**
 * `services/reporting-service/app/api/reports.py` — confirmed by source
 * inspection. `GET /reports` supports only `organization_id` (required),
 * `category`, `enabled_only` — no pagination, search, or sort exist on
 * this endpoint. `POST /reports/generate` is synchronous: it runs the
 * whole render+export pipeline inline and returns the finished result,
 * not a job handle to poll.
 */

import { apiClient } from "@/api/client";
import { fetchBinary, type BinaryDownload } from "@/features/reporting/lib/binary-fetch";
import type {
  ExportArtifact,
  ExportFormat,
  FilterClause,
  GenerateInput,
  GenerateResult,
  Report,
  ReportCategory,
  ReportCreateInput,
  ReportExecution,
  ReportExecutionStatusValue,
  ReportHistoryEntry,
  ReportTypeValue,
  ReportUpdateInput,
  ReportingStatistics,
} from "@/features/reporting/types";

interface ReportResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  template_id: string | null;
  name: string;
  description: string | null;
  category: ReportCategory;
  report_type: ReportTypeValue;
  default_format: ExportFormat;
  parameter_values: Record<string, unknown>;
  filters: FilterClause[];
  enabled: boolean;
  owner_id: string | null;
}

interface ExportSummaryBody {
  id: string;
  execution_id: string;
  export_format: ExportFormat;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  download_count: number;
}

interface ExecutionResponseBody {
  id: string;
  job_id: string;
  schedule_id: string | null;
  status: ReportExecutionStatusValue;
  row_count: number;
  section_count: number;
  duration_ms: number | null;
  error_message: string | null;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
}

interface GenerateResponseBody {
  execution: ExecutionResponseBody;
  exports: ExportSummaryBody[];
  degraded_sections: string[];
  distributions: string[];
  archive_id: string | null;
}

interface HistoryResponseBody {
  id: string;
  job_id: string;
  execution_id: string | null;
  event: string;
  summary: string;
  details: Record<string, unknown>;
  actor_id: string | null;
  occurred_at: string;
}

interface StatisticsResponseBody {
  total_reports: number;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  scheduled_executions: number;
  total_downloads: number;
  total_distributions: number;
  failed_distributions: number;
  average_duration_ms: number;
  popular_reports: Record<string, number>;
  export_format_usage: Record<string, number>;
  template_usage: Record<string, number>;
  schedule_usage: Record<string, number>;
  distribution_usage: Record<string, number>;
  computed_at: string;
}

function toReport(body: ReportResponseBody): Report {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    templateId: body.template_id,
    name: body.name,
    description: body.description,
    category: body.category,
    reportType: body.report_type,
    defaultFormat: body.default_format,
    parameterValues: body.parameter_values,
    filters: body.filters,
    enabled: body.enabled,
    ownerId: body.owner_id,
  };
}

function toExportArtifact(body: ExportSummaryBody): ExportArtifact {
  return {
    id: body.id,
    executionId: body.execution_id,
    exportFormat: body.export_format,
    filename: body.filename,
    contentType: body.content_type,
    sizeBytes: body.size_bytes,
    checksumSha256: body.checksum_sha256,
    downloadCount: body.download_count,
  };
}

function toExecution(body: ExecutionResponseBody): ReportExecution {
  return {
    id: body.id,
    jobId: body.job_id,
    scheduleId: body.schedule_id,
    status: body.status,
    rowCount: body.row_count,
    sectionCount: body.section_count,
    durationMs: body.duration_ms,
    errorMessage: body.error_message,
    triggeredBy: body.triggered_by,
    startedAt: body.started_at,
    finishedAt: body.finished_at,
  };
}

function toHistoryEntry(body: HistoryResponseBody): ReportHistoryEntry {
  return {
    id: body.id,
    jobId: body.job_id,
    executionId: body.execution_id,
    event: body.event,
    summary: body.summary,
    details: body.details,
    actorId: body.actor_id,
    occurredAt: body.occurred_at,
  };
}

function toStatistics(body: StatisticsResponseBody): ReportingStatistics {
  return {
    totalReports: body.total_reports,
    totalExecutions: body.total_executions,
    successfulExecutions: body.successful_executions,
    failedExecutions: body.failed_executions,
    scheduledExecutions: body.scheduled_executions,
    totalDownloads: body.total_downloads,
    totalDistributions: body.total_distributions,
    failedDistributions: body.failed_distributions,
    averageDurationMs: body.average_duration_ms,
    popularReports: body.popular_reports,
    exportFormatUsage: body.export_format_usage,
    templateUsage: body.template_usage,
    scheduleUsage: body.schedule_usage,
    distributionUsage: body.distribution_usage,
    computedAt: body.computed_at,
  };
}

export interface ReportListParams {
  organizationId: string;
  category?: ReportCategory;
  enabledOnly?: boolean;
}

export const reportsApi = {
  async list(params: ReportListParams): Promise<Report[]> {
    const query = new URLSearchParams({ organization_id: params.organizationId });
    if (params.category) query.set("category", params.category);
    if (params.enabledOnly) query.set("enabled_only", "true");
    const body = await apiClient.get<ReportResponseBody[]>(`/reports?${query.toString()}`);
    return body.map(toReport);
  },

  async getById(id: string): Promise<Report> {
    const body = await apiClient.get<ReportResponseBody>(`/reports/${encodeURIComponent(id)}`);
    return toReport(body);
  },

  async create(input: ReportCreateInput): Promise<Report> {
    const body = await apiClient.post<ReportResponseBody>("/reports", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      name: input.name,
      description: input.description,
      category: input.category,
      report_type: input.reportType,
      template_id: input.templateId,
      default_format: input.defaultFormat,
      parameter_values: input.parameterValues,
      filters: input.filters,
    });
    return toReport(body);
  },

  async update(id: string, input: ReportUpdateInput): Promise<Report> {
    const body = await apiClient.put<ReportResponseBody>(`/reports/${encodeURIComponent(id)}`, {
      name: input.name,
      description: input.description,
      default_format: input.defaultFormat,
      parameter_values: input.parameterValues,
      filters: input.filters,
      enabled: input.enabled,
    });
    return toReport(body);
  },

  /** A soft delete — `DELETE /reports/{id}` returns no body. */
  async remove(id: string): Promise<void> {
    await apiClient.delete<null>(`/reports/${encodeURIComponent(id)}`);
  },

  async generate(input: GenerateInput): Promise<GenerateResult> {
    const body = await apiClient.post<GenerateResponseBody>("/reports/generate", {
      report_id: input.reportId,
      export_formats: input.exportFormats,
      parameter_values: input.parameterValues,
      filters: input.filters,
      distribute: input.distribute,
      archive: input.archive,
      signed_by: input.signedBy,
      pdf_password: input.pdfPassword,
    });
    return {
      execution: toExecution(body.execution),
      exports: body.exports.map(toExportArtifact),
      degradedSections: body.degraded_sections,
      distributions: body.distributions,
      archiveId: body.archive_id,
    };
  },

  /** `POST /reports/export` re-renders an existing execution into a new
   * format — it does not convert bytes from one format to another. */
  async exportExisting(executionId: string, format: ExportFormat, options?: { signedBy?: string; pdfPassword?: string }): Promise<ExportArtifact> {
    const body = await apiClient.post<ExportSummaryBody>("/reports/export", {
      execution_id: executionId,
      export_format: format,
      signed_by: options?.signedBy,
      pdf_password: options?.pdfPassword,
    });
    return toExportArtifact(body);
  },

  async listExecutionExports(executionId: string): Promise<ExportArtifact[]> {
    const body = await apiClient.get<ExportSummaryBody[]>(`/reports/executions/${encodeURIComponent(executionId)}/exports`);
    return body.map(toExportArtifact);
  },

  downloadExport(exportId: string, fallbackFilename: string): Promise<BinaryDownload> {
    return fetchBinary(`/reports/exports/${encodeURIComponent(exportId)}/download`, fallbackFilename);
  },

  async favorite(reportId: string): Promise<void> {
    await apiClient.post<null>(`/reports/${encodeURIComponent(reportId)}/favorite`);
  },

  async unfavorite(reportId: string): Promise<void> {
    await apiClient.delete<null>(`/reports/${encodeURIComponent(reportId)}/favorite`);
  },

  async listFavorites(organizationId: string): Promise<Report[]> {
    const body = await apiClient.get<ReportResponseBody[]>(`/reports/favorites/mine?organization_id=${encodeURIComponent(organizationId)}`);
    return body.map(toReport);
  },

  async listHistory(organizationId: string, options?: { reportId?: string; limit?: number }): Promise<ReportHistoryEntry[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (options?.reportId) query.set("report_id", options.reportId);
    if (options?.limit) query.set("limit", String(options.limit));
    const body = await apiClient.get<HistoryResponseBody[]>(`/reports/history?${query.toString()}`);
    return body.map(toHistoryEntry);
  },

  async statistics(organizationId: string, recompute = false): Promise<ReportingStatistics> {
    const query = new URLSearchParams({ organization_id: organizationId, recompute: String(recompute) });
    const body = await apiClient.get<StatisticsResponseBody>(`/reports/statistics?${query.toString()}`);
    return toStatistics(body);
  },
};
