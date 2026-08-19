/**
 * `services/inventory-service/app/api/export.py` — confirmed by
 * source inspection. Genuinely async: `POST /inventory/export` returns
 * `202` and queues a background job — the caller polls
 * `GET /inventory/export/{id}` until `downloadUrl` is set, then opens
 * that presigned URL directly (never routed back through `apiClient`,
 * since it's already a self-authenticating link to object storage).
 */

import { apiClient } from "@/api/client";
import type { CreateExportInput, ExportFormatValue, ExportJob, ImportExportJobStatusValue } from "@/features/infrastructure/types";

interface ExportJobResponseBody {
  job_id: string;
  status: ImportExportJobStatusValue;
  target_format: ExportFormatValue;
  total_rows: number;
  download_url: string | null;
  started_at: string | null;
  completed_at: string | null;
}

function toExportJob(body: ExportJobResponseBody): ExportJob {
  return {
    jobId: body.job_id,
    status: body.status,
    targetFormat: body.target_format,
    totalRows: body.total_rows,
    downloadUrl: body.download_url,
    startedAt: body.started_at,
    completedAt: body.completed_at,
  };
}

export const exportApi = {
  async create(input: CreateExportInput): Promise<ExportJob> {
    const body = await apiClient.post<ExportJobResponseBody>("/inventory/export", {
      organization_id: input.organizationId,
      target_format: input.targetFormat ?? "json",
      asset_type: input.assetType,
      status: input.status,
      tags: input.tags ?? [],
    });
    return toExportJob(body);
  },

  async getById(jobId: string): Promise<ExportJob> {
    const body = await apiClient.get<ExportJobResponseBody>(`/inventory/export/${encodeURIComponent(jobId)}`);
    return toExportJob(body);
  },
};
