import { useMemo } from "react";

import { useAllAssets, useAsset } from "@/features/infrastructure/hooks/use-assets";
import { useTopology } from "@/features/infrastructure/hooks/use-topology";
import { buildFocusGraph } from "@/features/infrastructure/lib/topology-graph-adapter";
import type { AssetHealthValue } from "@/features/infrastructure/types";

/**
 * Composes three real queries into one `TopologyGraph` (§29 "API
 * Architecture" / §30 "Graph Adapter"): the focused asset's own
 * identity, its real 1-hop neighbors, and the organization's asset
 * list (for the health overlay join — §9). Health is best-effort: if
 * `useAllAssets` is slow or fails, the graph still renders with
 * `health: null` per node rather than blocking on it (§42 partial
 * failure).
 */
export function useTopologyGraph(focusAssetId: string | null, organizationId: string | null) {
  const rootQuery = useAsset(focusAssetId);
  const neighborsQuery = useTopology(focusAssetId, "neighbors");
  const allAssetsQuery = useAllAssets(organizationId);

  const healthById = useMemo(() => {
    const map = new Map<string, AssetHealthValue>();
    for (const asset of allAssetsQuery.data ?? []) map.set(asset.id, asset.health);
    return map;
  }, [allAssetsQuery.data]);

  const graph = useMemo(() => {
    if (!rootQuery.data || !neighborsQuery.data) return null;
    return buildFocusGraph(rootQuery.data, neighborsQuery.data, healthById);
  }, [rootQuery.data, neighborsQuery.data, healthById]);

  return {
    graph,
    isLoading: rootQuery.isLoading || neighborsQuery.isLoading,
    isError: rootQuery.isError || neighborsQuery.isError,
    error: rootQuery.error ?? neighborsQuery.error,
    refetch: () => {
      void rootQuery.refetch();
      void neighborsQuery.refetch();
    },
  };
}
