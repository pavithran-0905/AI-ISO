import { useQuery } from "@tanstack/react-query";

import { assetsApi } from "@/features/monitoring/api/assets-api";

export function useAssetRelationships(assetId: string | null) {
  return useQuery({
    queryKey: ["monitoring", "assets", assetId, "relationships"],
    queryFn: () => assetsApi.fetchRelationships(assetId as string),
    enabled: assetId !== null,
    staleTime: 60_000,
  });
}
