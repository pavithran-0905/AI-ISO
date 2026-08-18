import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { jobsApi } from "@/features/automation/api/jobs-api";
import { statisticsApi } from "@/features/automation/api/statistics-api";
import type {
  AutomationJobCreateInput,
  AutomationJobUpdateInput,
  RunAutomationInput,
} from "@/features/automation/types";

export function useAutomationJobs(organizationId: string | null) {
  return useQuery({
    queryKey: ["automation", "jobs", organizationId],
    queryFn: () => jobsApi.list(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useAutomationJob(jobId: string | null) {
  return useQuery({
    queryKey: ["automation", "jobs", jobId],
    queryFn: () => jobsApi.getById(jobId as string),
    enabled: jobId !== null,
    staleTime: 15_000,
  });
}

export function useAutomationStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["automation", "statistics", organizationId],
    queryFn: () => statisticsApi.fetch(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

/**
 * Every mutation below waits for the backend's confirmed response
 * before the UI reflects it (§32: "do not use unsafe optimistic
 * updates for infrastructure operations"). Automation can change real
 * infrastructure, so showing a state the backend hasn't confirmed is
 * materially worse here than in a read-mostly feature.
 */
export function useCreateAutomationJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AutomationJobCreateInput) => jobsApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "jobs"] });
    },
  });
}

export function useUpdateAutomationJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AutomationJobUpdateInput) => jobsApi.update(jobId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "jobs"] });
    },
  });
}

export function useDeleteAutomationJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => jobsApi.remove(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "jobs"] });
    },
  });
}

/** Returns a `pending` execution — the real run happens on a queue
 * worker, so the caller navigates to the execution and polls it. */
export function useRunAutomation(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RunAutomationInput) => jobsApi.run(jobId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "executions"] });
    },
  });
}

/** Cancel/pause/resume all act on the job's own currently-active
 * execution — the backend resolves which one, there is no
 * per-execution variant of these routes. */
export function useCancelAutomation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => jobsApi.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "executions"] });
    },
  });
}

export function usePauseAutomation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => jobsApi.pause(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "executions"] });
    },
  });
}

export function useResumeAutomation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => jobsApi.resume(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", "executions"] });
    },
  });
}
