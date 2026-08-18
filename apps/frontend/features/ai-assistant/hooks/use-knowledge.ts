import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { knowledgeApi } from "@/features/ai-assistant/api/knowledge-api";
import type { IngestDocumentInput, KnowledgeSearchInput } from "@/features/ai-assistant/types";

export function useKnowledgeDocuments(organizationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "knowledge", "documents", organizationId],
    queryFn: () => knowledgeApi.listDocuments(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useIngestDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: IngestDocumentInput) => knowledgeApi.ingest(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "knowledge", "documents"] });
    },
  });
}

/** A search, not a list — results are query-shaped, not cacheable by a
 * stable key a list view would reuse, so this is a mutation rather
 * than a `useQuery`, matching the composer-driven, one-shot nature of
 * the search panel. */
export function useKnowledgeSearch() {
  return useMutation({
    mutationFn: (input: KnowledgeSearchInput) => knowledgeApi.search(input),
  });
}
