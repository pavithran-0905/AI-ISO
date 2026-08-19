import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { importApi } from "@/features/infrastructure/api/import-api";
import { ACTIVE_JOB_STATUSES, type CreateImportInput, type ImportJob } from "@/features/infrastructure/types";

const ACTIVE_POLL_MS = 3_000;

export function useCreateImport() {
  return useMutation({
    mutationFn: (input: CreateImportInput) => importApi.create(input),
  });
}

export function useImportJob(jobId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "import", jobId],
    queryFn: () => importApi.getById(jobId as string),
    enabled: jobId !== null,
    staleTime: 0,
    refetchInterval: (query) => {
      const job = query.state.data as ImportJob | undefined;
      if (!job) return false;
      return ACTIVE_JOB_STATUSES.has(job.status) ? ACTIVE_POLL_MS : false;
    },
  });
}

/** A rollback undoes a completed, non-preview import — the asset list
 * it touched is invalidated afterward since assets it created will
 * disappear. */
export function useRollbackImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => importApi.rollback(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "assets"] });
    },
  });
}
