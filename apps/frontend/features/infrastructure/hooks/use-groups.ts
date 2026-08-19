import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { groupsApi } from "@/features/infrastructure/api/groups-api";
import type { CreateGroupInput } from "@/features/infrastructure/types";

export function useGroups(organizationId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "groups", organizationId],
    queryFn: () => groupsApi.list(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useGroupMembers(groupId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "groups", groupId, "members"],
    queryFn: () => groupsApi.members(groupId as string),
    enabled: groupId !== null,
    staleTime: 30_000,
  });
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateGroupInput) => groupsApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "groups"] });
    },
  });
}
