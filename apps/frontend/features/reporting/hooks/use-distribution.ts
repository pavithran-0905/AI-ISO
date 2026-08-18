import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { distributionApi } from "@/features/reporting/api/distribution-api";
import type { DistributeInput, DistributionStatusValue, RecipientCreateInput } from "@/features/reporting/types";

export function useRecipients(reportId: string | null) {
  return useQuery({
    queryKey: ["reporting", "recipients", reportId],
    queryFn: () => distributionApi.listRecipients(reportId as string),
    enabled: reportId !== null,
    staleTime: 30_000,
  });
}

export function useDistributionsForExport(exportId: string | null) {
  return useQuery({
    queryKey: ["reporting", "distributions", "export", exportId],
    queryFn: () => distributionApi.listDistributionsForExport(exportId as string),
    enabled: exportId !== null,
    staleTime: 15_000,
  });
}

export function useDistributions(organizationId: string | null, options?: { status?: DistributionStatusValue; limit?: number }) {
  return useQuery({
    queryKey: ["reporting", "distributions", organizationId, options],
    queryFn: () => distributionApi.listDistributions(organizationId as string, options),
    enabled: organizationId !== null,
    staleTime: 15_000,
  });
}

export function useCreateRecipient(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RecipientCreateInput) => distributionApi.createRecipient(reportId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "recipients", reportId] });
    },
  });
}

export function useDeleteRecipient(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (recipientId: string) => distributionApi.removeRecipient(recipientId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "recipients", reportId] });
    },
  });
}

export function useDistributeExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ exportId, input }: { exportId: string; input: DistributeInput }) => distributionApi.distribute(exportId, input),
    onSuccess: (_result, { exportId }) => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "distributions", "export", exportId] });
      queryClient.invalidateQueries({ queryKey: ["reporting", "distributions"] });
    },
  });
}

export function useShareExport() {
  return useMutation({
    mutationFn: (exportId: string) => distributionApi.share(exportId),
  });
}
