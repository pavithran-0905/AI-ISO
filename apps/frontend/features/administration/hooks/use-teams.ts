import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { teamsApi } from "@/features/administration/api/teams-api";
import type { CreateTeamInput, UpdateTeamInput } from "@/features/administration/types";

export function useTeams(organizationId: string | null) {
  return useQuery({
    queryKey: ["administration", "teams", organizationId],
    queryFn: () => teamsApi.listForOrganization(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateTeamInput) => teamsApi.create(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "teams"] }),
  });
}

export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, input }: { teamId: string; input: UpdateTeamInput }) => teamsApi.update(teamId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "teams"] }),
  });
}

export function useRemoveTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (teamId: string) => teamsApi.remove(teamId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "teams"] }),
  });
}
