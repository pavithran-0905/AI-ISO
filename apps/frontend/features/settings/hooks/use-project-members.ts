import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { projectMembersApi } from "@/features/settings/api/project-members-api";
import type { AddProjectMemberInput, UpdateProjectMemberRoleInput } from "@/features/settings/types";

export function useProjectMembers(projectId: string | null) {
  return useQuery({
    queryKey: ["settings", "projects", projectId, "members"],
    queryFn: () => projectMembersApi.list(projectId as string),
    enabled: projectId !== null,
    staleTime: 15_000,
  });
}

export function useAddProjectMember(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AddProjectMemberInput) => projectMembersApi.add(projectId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "projects", projectId, "members"] }),
  });
}

export function useUpdateProjectMemberRole(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, input }: { userId: string; input: UpdateProjectMemberRoleInput }) =>
      projectMembersApi.updateRole(projectId, userId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "projects", projectId, "members"] }),
  });
}

export function useRemoveProjectMember(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => projectMembersApi.remove(projectId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "projects", projectId, "members"] }),
  });
}
