import { useQuery } from "@tanstack/react-query";

import { topologyApi } from "@/features/infrastructure/api/topology-api";
import type { TopologyQueryKindValue } from "@/features/infrastructure/types";

export function useTopology(assetId: string | null, queryKind: TopologyQueryKindValue, depth?: number) {
  return useQuery({
    queryKey: ["infrastructure", "topology", assetId, queryKind, depth],
    queryFn: () => topologyApi.get(assetId as string, queryKind, depth),
    enabled: assetId !== null,
    staleTime: 30_000,
  });
}
