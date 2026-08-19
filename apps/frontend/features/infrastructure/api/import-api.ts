/**
 * `services/inventory-service/app/api/import_.py` — confirmed by
 * source inspection. `POST /inventory/import` is `multipart/form-data`
 * (see `lib/multipart-fetch.ts`) with `organization_id`/`source_format`/
 * `preview_only` as query params, not form fields. Genuinely async
 * (`202`, queued) — the caller polls `GET /inventory/import/{id}`.
 */

import { apiClient } from "@/api/client";
import { postMultipart } from "@/features/infrastructure/lib/multipart-fetch";
import type { CreateImportInput, ImportExportJobStatusValue, ImportFormatValue, ImportJob } from "@/features/infrastructure/types";

interface ImportJobResponseBody {
  job_id: string;
  status: ImportExportJobStatusValue;
  source_format: ImportFormatValue;
  preview_only: boolean;
  total_rows: number;
  processed_rows: number;
  succeeded_rows: number;
  failed_rows: number;
  duplicate_rows: number;
  error_report: Record<string, unknown>[];
  started_at: string | null;
  completed_at: string | null;
}

function toImportJob(body: ImportJobResponseBody): ImportJob {
  return {
    jobId: body.job_id,
    status: body.status,
    sourceFormat: body.source_format,
    previewOnly: body.preview_only,
    totalRows: body.total_rows,
    processedRows: body.processed_rows,
    succeededRows: body.succeeded_rows,
    failedRows: body.failed_rows,
    duplicateRows: body.duplicate_rows,
    errorReport: body.error_report,
    startedAt: body.started_at,
    completedAt: body.completed_at,
  };
}

export const importApi = {
  async create(input: CreateImportInput): Promise<ImportJob> {
    const query = new URLSearchParams({
      organization_id: input.organizationId,
      source_format: input.sourceFormat ?? "json",
      preview_only: String(input.previewOnly ?? false),
    });
    const body = await postMultipart<ImportJobResponseBody>(`/inventory/import?${query.toString()}`, input.file);
    return toImportJob(body);
  },

  async getById(jobId: string): Promise<ImportJob> {
    const body = await apiClient.get<ImportJobResponseBody>(`/inventory/import/${encodeURIComponent(jobId)}`);
    return toImportJob(body);
  },

  async rollback(jobId: string): Promise<ImportJob> {
    const body = await apiClient.post<ImportJobResponseBody>(`/inventory/import/${encodeURIComponent(jobId)}/rollback`, {});
    return toImportJob(body);
  },
};
