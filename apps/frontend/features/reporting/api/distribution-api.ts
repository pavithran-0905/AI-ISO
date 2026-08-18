/**
 * `services/reporting-service/app/api/delivery.py`'s recipient/
 * distribution/share routes — confirmed by source inspection.
 * `share_token` is only ever present on the response to the create
 * call itself (`ShareLinkResponse`) — `DistributionResponse` (the list/
 * detail shape) never includes it, and there is no revoke endpoint.
 */

import { apiClient } from "@/api/client";
import type {
  DistributeInput,
  DistributionChannelValue,
  DistributionStatusValue,
  ExportFormat,
  RecipientCreateInput,
  ReportDistribution,
  ReportRecipient,
  ShareLink,
} from "@/features/reporting/types";

interface RecipientResponseBody {
  id: string;
  job_id: string;
  channel: DistributionChannelValue;
  target: string;
  export_format: ExportFormat;
  headers: Record<string, string>;
  enabled: boolean;
}

interface DistributionResponseBody {
  id: string;
  export_id: string;
  recipient_id: string | null;
  channel: DistributionChannelValue;
  target: string;
  status: DistributionStatusValue;
  attempts: number;
  expires_at: string | null;
  storage_uri: string | null;
  error_message: string | null;
  delivered_at: string | null;
}

interface ShareLinkResponseBody {
  distribution_id: string;
  share_token: string;
  expires_at: string | null;
}

function toRecipient(body: RecipientResponseBody): ReportRecipient {
  return {
    id: body.id,
    jobId: body.job_id,
    channel: body.channel,
    target: body.target,
    exportFormat: body.export_format,
    headers: body.headers,
    enabled: body.enabled,
  };
}

function toDistribution(body: DistributionResponseBody): ReportDistribution {
  return {
    id: body.id,
    exportId: body.export_id,
    recipientId: body.recipient_id,
    channel: body.channel,
    target: body.target,
    status: body.status,
    attempts: body.attempts,
    expiresAt: body.expires_at,
    storageUri: body.storage_uri,
    errorMessage: body.error_message,
    deliveredAt: body.delivered_at,
  };
}

function toShareLink(body: ShareLinkResponseBody): ShareLink {
  return { distributionId: body.distribution_id, shareToken: body.share_token, expiresAt: body.expires_at };
}

export const distributionApi = {
  async listRecipients(reportId: string): Promise<ReportRecipient[]> {
    const body = await apiClient.get<RecipientResponseBody[]>(`/reports/${encodeURIComponent(reportId)}/recipients`);
    return body.map(toRecipient);
  },

  async createRecipient(reportId: string, input: RecipientCreateInput): Promise<ReportRecipient> {
    const body = await apiClient.post<RecipientResponseBody>(`/reports/${encodeURIComponent(reportId)}/recipients`, {
      organization_id: input.organizationId,
      project_id: input.projectId,
      channel: input.channel,
      target: input.target,
      export_format: input.exportFormat,
      headers: input.headers,
    });
    return toRecipient(body);
  },

  async removeRecipient(recipientId: string): Promise<void> {
    await apiClient.delete<null>(`/reports/recipients/${encodeURIComponent(recipientId)}`);
  },

  async distribute(exportId: string, input: DistributeInput): Promise<ReportDistribution> {
    const body = await apiClient.post<DistributionResponseBody>(`/reports/exports/${encodeURIComponent(exportId)}/distribute`, {
      channel: input.channel,
      target: input.target,
      headers: input.headers,
    });
    return toDistribution(body);
  },

  /** Mints a share link — the returned token is shown exactly once. */
  async share(exportId: string): Promise<ShareLink> {
    const body = await apiClient.post<ShareLinkResponseBody>(`/reports/exports/${encodeURIComponent(exportId)}/share`);
    return toShareLink(body);
  },

  async listDistributionsForExport(exportId: string): Promise<ReportDistribution[]> {
    const body = await apiClient.get<DistributionResponseBody[]>(`/reports/exports/${encodeURIComponent(exportId)}/distributions`);
    return body.map(toDistribution);
  },

  async listDistributions(organizationId: string, options?: { status?: DistributionStatusValue; limit?: number }): Promise<ReportDistribution[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (options?.status) query.set("status", options.status);
    if (options?.limit) query.set("limit", String(options.limit));
    const body = await apiClient.get<DistributionResponseBody[]>(`/reports/distributions?${query.toString()}`);
    return body.map(toDistribution);
  },
};
