import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { schedulesApi } from "@/features/reporting/api/schedules-api";
import type { ScheduleCreateInput, ScheduleUpdateInput } from "@/features/reporting/types";

export function useSchedules(organizationId: string | null, reportId?: string) {
  return useQuery({
    queryKey: ["reporting", "schedules", organizationId, reportId],
    queryFn: () => schedulesApi.list(organizationId as string, reportId),
    enabled: organizationId !== null,
    staleTime: 15_000,
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ScheduleCreateInput) => schedulesApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "schedules"] });
    },
  });
}

export function useUpdateSchedule(scheduleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ScheduleUpdateInput) => schedulesApi.update(scheduleId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "schedules"] });
    },
  });
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: string) => schedulesApi.remove(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "schedules"] });
    },
  });
}
