import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { assetsApi } from "@/features/monitoring/api/assets-api";
import type { AssetSearchParams } from "@/features/monitoring/types";

export function useAssetSearch(params: AssetSearchParams | null) {
  return useQuery({
    queryKey: ["monitoring", "assets", "search", params],
    queryFn: () => assetsApi.search(params as AssetSearchParams),
    enabled: params !== null,
    staleTime: 30_000,
    // Keeps the current page's rows visible while the next page/filter
    // loads, instead of the table flashing to a skeleton on every
    // pagination click (§32/§35's "avoid page-wide blocking loaders").
    placeholderData: keepPreviousData,
  });
}
