import { useMutation, useQuery } from "@tanstack/react-query";

import { exportApi } from "@/features/infrastructure/api/export-api";
import { ACTIVE_JOB_STATUSES, type CreateExportInput, type ExportJob } from "@/features/infrastructure/types";

/** `inventory-service` exposes no WebSocket or SSE endpoint for job
 * progress (confirmed by source inspection) — polling is the only way
 * to follow one. Stops the moment the job reaches a terminal status. */
const ACTIVE_POLL_MS = 3_000;

export function useCreateExport() {
  return useMutation({
    mutationFn: (input: CreateExportInput) => exportApi.create(input),
  });
}

export function useExportJob(jobId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "export", jobId],
    queryFn: () => exportApi.getById(jobId as string),
    enabled: jobId !== null,
    staleTime: 0,
    refetchInterval: (query) => {
      const job = query.state.data as ExportJob | undefined;
      if (!job) return false;
      return ACTIVE_JOB_STATUSES.has(job.status) ? ACTIVE_POLL_MS : false;
    },
  });
}
