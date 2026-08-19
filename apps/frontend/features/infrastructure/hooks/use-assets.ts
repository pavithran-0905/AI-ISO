import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { assetsApi } from "@/features/infrastructure/api/assets-api";
import type { AssetSearchParams, CreateAssetInput, PatchAssetInput } from "@/features/infrastructure/types";

export function useAssetSearch(params: AssetSearchParams | null) {
  return useQuery({
    queryKey: ["infrastructure", "assets", "search", params],
    queryFn: () => assetsApi.search(params as AssetSearchParams),
    enabled: params !== null,
    staleTime: 30_000,
    // Keeps the current page's rows visible while the next page/filter
    // loads, instead of the table flashing to a skeleton on every
    // pagination click.
    placeholderData: keepPreviousData,
  });
}

/** Unbounded — only for a relationship-target picker or similar,
 * never a primary list view. See `assetsApi.listAll`'s own docstring. */
export function useAllAssets(organizationId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "assets", "all", organizationId],
    queryFn: () => assetsApi.listAll(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useAsset(assetId: string | null) {
  return useQuery({
    queryKey: ["infrastructure", "assets", assetId],
    queryFn: () => assetsApi.getById(assetId as string),
    enabled: assetId !== null,
    staleTime: 15_000,
  });
}

/** Every mutation waits for the backend's confirmed response before
 * the UI reflects it — no optimistic updates for infrastructure
 * mutations (§22: "do not use optimistic updates for high-impact
 * infrastructure changes"). */
export function useCreateAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateAssetInput) => assetsApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "assets"] });
    },
  });
}

export function usePatchAsset(assetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PatchAssetInput) => assetsApi.patch(assetId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "assets"] });
    },
  });
}

export function useDeleteAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) => assetsApi.remove(assetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "assets"] });
    },
  });
}
