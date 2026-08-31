import { useMutation, useQuery } from "@tanstack/react-query";

import { auditApi } from "@/features/audit/api/audit-api";
import type { AuditEventSearchParams, AuditReportRequest, AuditSourceValue } from "@/features/audit/types";

export function useAuditEvents(source: AuditSourceValue, params: AuditEventSearchParams | null) {
  return useQuery({
    queryKey: ["audit", "events", source, params],
    queryFn: () => auditApi.search(source, params as AuditEventSearchParams),
    enabled: params !== null,
    staleTime: 15_000,
  });
}

export function useComplianceAuditSummary(organizationId: string | null, days = 30) {
  return useQuery({
    queryKey: ["audit", "compliance", "summary", organizationId, days],
    queryFn: () => auditApi.getComplianceSummary(organizationId as string, days),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useNotificationsAuditSummary(organizationId: string | null, days = 30) {
  return useQuery({
    queryKey: ["audit", "notifications", "summary", organizationId, days],
    queryFn: () => auditApi.getNotificationsSummary(organizationId as string, days),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useFindingsSummary(organizationId: string | null) {
  return useQuery({
    queryKey: ["audit", "findings", "summary", organizationId],
    queryFn: () => auditApi.getFindingsSummary(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

/** Generates and immediately downloads a compliance audit report —
 * one combined action, since the backend call itself is already
 * synchronous (see `AuditReportResult`'s docstring). */
export function useExportComplianceAudit() {
  return useMutation({
    mutationFn: async (params: AuditReportRequest) => {
      const report = await auditApi.generateAuditReport(params);
      if (report.status !== "completed") {
        throw new Error(report.error ?? `Report generation ended with status "${report.status}".`);
      }
      const extension = params.reportFormat === "csv" ? "csv" : params.reportFormat === "markdown" ? "md" : "json";
      await auditApi.downloadAuditReport(params.organizationId, report.id, `audit-report.${extension}`);
      return report;
    },
  });
}
