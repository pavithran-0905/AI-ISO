import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { archiveApi } from "@/features/reporting/api/archive-api";
import { saveBlob } from "@/features/reporting/lib/binary-fetch";
import type { ArchiveCreateInput, ArchiveStatusValue } from "@/features/reporting/types";

export function useArchivedReports(organizationId: string | null, options?: { search?: string; status?: ArchiveStatusValue; limit?: number }) {
  return useQuery({
    queryKey: ["reporting", "archive", organizationId, options],
    queryFn: () => archiveApi.list(organizationId as string, options),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useCreateArchive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ArchiveCreateInput) => archiveApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "archive"] });
    },
  });
}

export function useDownloadArchive() {
  return useMutation({
    mutationFn: async ({ archiveId, filename }: { archiveId: string; filename: string }) => {
      const download = await archiveApi.download(archiveId, filename);
      saveBlob(download);
      return download;
    },
  });
}

export function useRestoreArchive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (archiveId: string) => archiveApi.restore(archiveId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "archive"] });
    },
  });
}

export function usePurgeArchive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ archiveId, reason }: { archiveId: string; reason?: string }) => archiveApi.purge(archiveId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "archive"] });
    },
  });
}
