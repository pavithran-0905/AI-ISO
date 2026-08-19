import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { relationshipsApi } from "@/features/infrastructure/api/relationships-api";
import type { CreateRelationshipInput } from "@/features/infrastructure/types";

export function useAssetRelationships(assetId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "relationships", assetId],
    queryFn: () => relationshipsApi.listForAsset(assetId as string),
    enabled: assetId !== null,
    staleTime: 30_000,
  });
}

export function useCreateRelationship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateRelationshipInput) => relationshipsApi.create(input),
    onSuccess: (_data, input) => {
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "relationships", input.sourceAssetId] });
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "relationships", input.targetAssetId] });
    },
  });
}

export function useDeleteRelationship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (relationshipId: string) => relationshipsApi.remove(relationshipId),
    onSuccess: () => {
      // The relationship id alone doesn't say which two assets it
      // touched, so every cached relationship list is invalidated
      // rather than guessing which one to target.
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "relationships"] });
    },
  });
}
