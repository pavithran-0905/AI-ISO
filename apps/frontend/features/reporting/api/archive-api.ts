/**
 * `services/reporting-service/app/api/delivery.py`'s archive routes —
 * confirmed by source inspection. Archived artifacts keep their own
 * copy of bytes+checksum (not a reference to the live export), so
 * purging or regenerating a report can't retroactively alter what was
 * archived. Purge zeroes the content and flips `status`; it never
 * deletes the row (audit trail).
 */

import { apiClient } from "@/api/client";
import { fetchBinary, type BinaryDownload } from "@/features/reporting/lib/binary-fetch";
import type { ArchiveCreateInput, ArchiveStatusValue, ArchivedReport, ExportFormat } from "@/features/reporting/types";

interface ArchiveResponseBody {
  id: string;
  execution_id: string | null;
  job_id: string | null;
  title: string;
  export_format: ExportFormat;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  archive_version: number;
  status: ArchiveStatusValue;
  archived_at: string;
  retention_until: string | null;
  purge_reason: string | null;
}

function toArchivedReport(body: ArchiveResponseBody): ArchivedReport {
  return {
    id: body.id,
    executionId: body.execution_id,
    jobId: body.job_id,
    title: body.title,
    exportFormat: body.export_format,
    filename: body.filename,
    contentType: body.content_type,
    sizeBytes: body.size_bytes,
    checksumSha256: body.checksum_sha256,
    archiveVersion: body.archive_version,
    status: body.status,
    archivedAt: body.archived_at,
    retentionUntil: body.retention_until,
    purgeReason: body.purge_reason,
  };
}

export const archiveApi = {
  async list(organizationId: string, options?: { search?: string; status?: ArchiveStatusValue; limit?: number }): Promise<ArchivedReport[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (options?.search) query.set("search", options.search);
    if (options?.status) query.set("status", options.status);
    if (options?.limit) query.set("limit", String(options.limit));
    const body = await apiClient.get<ArchiveResponseBody[]>(`/reports/archive?${query.toString()}`);
    return body.map(toArchivedReport);
  },

  async create(input: ArchiveCreateInput): Promise<ArchivedReport> {
    const body = await apiClient.post<ArchiveResponseBody>("/reports/archive", {
      export_id: input.exportId,
      title: input.title,
      retention_days: input.retentionDays,
    });
    return toArchivedReport(body);
  },

  download(archiveId: string, fallbackFilename: string): Promise<BinaryDownload> {
    return fetchBinary(`/reports/archive/${encodeURIComponent(archiveId)}/download`, fallbackFilename);
  },

  /** Creates a brand-new export from the archived bytes — never
   * resurrects the original export row. */
  async restore(archiveId: string): Promise<ArchivedReport> {
    const body = await apiClient.post<ArchiveResponseBody>(`/reports/archive/${encodeURIComponent(archiveId)}/restore`);
    return toArchivedReport(body);
  },

  /** Rejected with a 409 by the backend if still within the retention
   * window or already purged — surfaced as a normal `ApiRequestError`,
   * not specially handled here. */
  async purge(archiveId: string, reason?: string): Promise<ArchivedReport> {
    const query = reason ? `?reason=${encodeURIComponent(reason)}` : "";
    const body = await apiClient.delete<ArchiveResponseBody>(`/reports/archive/${encodeURIComponent(archiveId)}${query}`);
    return toArchivedReport(body);
  },
};
