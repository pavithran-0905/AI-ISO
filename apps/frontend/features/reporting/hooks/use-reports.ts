import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { reportsApi, type ReportListParams } from "@/features/reporting/api/reports-api";
import { saveBlob } from "@/features/reporting/lib/binary-fetch";
import type { GenerateInput, ReportCreateInput, ReportUpdateInput } from "@/features/reporting/types";

export function useReports(params: ReportListParams | null) {
  return useQuery({
    queryKey: ["reporting", "reports", params],
    queryFn: () => reportsApi.list(params as ReportListParams),
    enabled: params !== null,
    staleTime: 30_000,
  });
}

export function useReport(reportId: string | null) {
  return useQuery({
    queryKey: ["reporting", "reports", reportId],
    queryFn: () => reportsApi.getById(reportId as string),
    enabled: reportId !== null,
    staleTime: 15_000,
  });
}

export function useFavoriteReports(organizationId: string | null) {
  return useQuery({
    queryKey: ["reporting", "reports", "favorites", organizationId],
    queryFn: () => reportsApi.listFavorites(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useReportHistory(organizationId: string | null, options?: { reportId?: string; limit?: number }) {
  return useQuery({
    queryKey: ["reporting", "history", organizationId, options],
    queryFn: () => reportsApi.listHistory(organizationId as string, options),
    enabled: organizationId !== null,
    staleTime: 15_000,
  });
}

export function useReportingStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["reporting", "statistics", organizationId],
    queryFn: () => reportsApi.statistics(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useExecutionExports(executionId: string | null) {
  return useQuery({
    queryKey: ["reporting", "executions", executionId, "exports"],
    queryFn: () => reportsApi.listExecutionExports(executionId as string),
    enabled: executionId !== null,
    staleTime: 15_000,
  });
}

/** Every write below waits for the backend's confirmed response before
 * the UI reflects it — no optimistic update, since `reporting-service`
 * exposes no version/conflict information a rolled-back optimistic
 * update could reconcile against (see
 * `docs/frontend/backend-v1-integration-limitations.md`). */
export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReportCreateInput) => reportsApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "reports"] });
    },
  });
}

export function useUpdateReport(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReportUpdateInput) => reportsApi.update(reportId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "reports"] });
    },
  });
}

export function useDeleteReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reportId: string) => reportsApi.remove(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "reports"] });
    },
  });
}

export function useGenerateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GenerateInput) => reportsApi.generate(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "history"] });
      queryClient.invalidateQueries({ queryKey: ["reporting", "statistics"] });
    },
  });
}

/** Downloads and immediately saves the artifact — a binary GET, not
 * representable as cached `useQuery` data. */
export function useDownloadExport() {
  return useMutation({
    mutationFn: async ({ exportId, filename }: { exportId: string; filename: string }) => {
      const download = await reportsApi.downloadExport(exportId, filename);
      saveBlob(download);
      return download;
    },
  });
}

export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reportId, favorited }: { reportId: string; favorited: boolean }) =>
      favorited ? reportsApi.unfavorite(reportId) : reportsApi.favorite(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "reports", "favorites"] });
    },
  });
}
