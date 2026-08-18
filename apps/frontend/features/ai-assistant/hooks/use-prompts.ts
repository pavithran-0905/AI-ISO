import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { promptsApi } from "@/features/ai-assistant/api/prompts-api";
import type { AddPromptVersionInput, CreatePromptInput } from "@/features/ai-assistant/types";

export function usePrompts(organizationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "prompts", organizationId],
    queryFn: () => promptsApi.list(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function usePromptVersions(promptId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "prompts", promptId, "versions"],
    queryFn: () => promptsApi.listVersions(promptId as string),
    enabled: promptId !== null,
    staleTime: 15_000,
  });
}

export function useCreatePrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreatePromptInput) => promptsApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "prompts"] });
    },
  });
}

export function useAddPromptVersion(promptId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AddPromptVersionInput) => promptsApi.addVersion(promptId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "prompts", promptId, "versions"] });
    },
  });
}

export function useApprovePromptVersion(promptId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionNumber: string) => promptsApi.approveVersion(promptId, versionNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "prompts", promptId, "versions"] });
    },
  });
}

export function useRollbackPrompt(promptId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionNumber: string) => promptsApi.rollback(promptId, versionNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "prompts"] });
    },
  });
}

/** A one-shot render preview — not cached, matching `useKnowledgeSearch`'s
 * reasoning: the result is shaped by whatever variables were typed a
 * moment ago, not a stable resource a list view would reuse. */
export function useRenderPrompt(promptId: string) {
  return useMutation({
    mutationFn: (variables: Record<string, string>) => promptsApi.render(promptId, variables),
  });
}
