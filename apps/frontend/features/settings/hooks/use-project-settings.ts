import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { projectApi } from "@/features/settings/api/project-api";
import type { PatchProjectInput, UpdateProjectSettingsInput } from "@/features/settings/types";

/** Unbounded, picker-only — see `projectApi.listForOrganization`'s
 * own docstring. */
export function useOrganizationProjects(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "projects", organizationId],
    queryFn: () => projectApi.listForOrganization(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function usePatchProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, input }: { projectId: string; input: PatchProjectInput }) => projectApi.patch(projectId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "projects"] }),
  });
}

export function useProjectSettings(projectId: string | null) {
  return useQuery({
    queryKey: ["settings", "projects", projectId, "settings"],
    queryFn: () => projectApi.getSettings(projectId as string),
    enabled: projectId !== null,
    staleTime: 60_000,
  });
}

export function useUpdateProjectSettings(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateProjectSettingsInput) => projectApi.updateSettings(projectId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "projects", projectId, "settings"] }),
  });
}
