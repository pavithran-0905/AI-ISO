import { useQuery } from "@tanstack/react-query";

import { assetsApi } from "@/features/monitoring/api/assets-api";

export function useAsset(assetId: string | null) {
  return useQuery({
    queryKey: ["monitoring", "assets", assetId],
    queryFn: () => assetsApi.getById(assetId as string),
    enabled: assetId !== null,
    staleTime: 30_000,
  });
}
