import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { systemApi } from "@/features/settings/api/system-api";
import type { CreateFeatureFlagInput, EnqueueSystemJobInput, UpdateFeatureFlagInput, UpsertPlatformSettingInput } from "@/features/settings/types";

export function useAdminDashboard() {
  return useQuery({ queryKey: ["settings", "system", "dashboard"], queryFn: systemApi.getDashboard, staleTime: 30_000 });
}

export function usePlatformSettings() {
  return useQuery({ queryKey: ["settings", "system", "settings"], queryFn: systemApi.listSettings, staleTime: 30_000 });
}

export function useUpsertPlatformSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpsertPlatformSettingInput) => systemApi.upsertSetting(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "system", "settings"] }),
  });
}

export function useFeatureFlags() {
  return useQuery({ queryKey: ["settings", "system", "feature-flags"], queryFn: systemApi.listFeatureFlags, staleTime: 30_000 });
}

export function useCreateFeatureFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateFeatureFlagInput) => systemApi.createFeatureFlag(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "system", "feature-flags"] }),
  });
}

export function useUpdateFeatureFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ flagId, input }: { flagId: string; input: UpdateFeatureFlagInput }) =>
      systemApi.updateFeatureFlag(flagId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "system", "feature-flags"] }),
  });
}

export function useSystemJobs() {
  return useQuery({ queryKey: ["settings", "system", "jobs"], queryFn: systemApi.listJobs, staleTime: 15_000 });
}

export function useEnqueueSystemJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EnqueueSystemJobInput) => systemApi.enqueueJob(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "system", "jobs"] }),
  });
}

export function useSystemDiagnostics() {
  return useQuery({ queryKey: ["settings", "system", "diagnostics"], queryFn: systemApi.listDiagnostics, staleTime: 30_000 });
}

export function useSystemHealth() {
  return useQuery({ queryKey: ["settings", "system", "health"], queryFn: systemApi.getHealth, staleTime: 30_000 });
}

export function useSystemStatistics() {
  return useQuery({ queryKey: ["settings", "system", "statistics"], queryFn: systemApi.getStatistics, staleTime: 60_000 });
}

export function useSystemReports() {
  return useQuery({ queryKey: ["settings", "system", "reports"], queryFn: systemApi.listReports, staleTime: 60_000 });
}
