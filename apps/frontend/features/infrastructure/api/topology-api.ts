/**
 * `services/inventory-service/app/api/topology.py` — confirmed by
 * source inspection. Rendered as a structured list, never a graph —
 * §15 explicitly defers graph visualization to a future feature when
 * topology data exists but graph UX isn't appropriate here, and §53
 * forbids adding a graph library for this one view.
 */

import { apiClient } from "@/api/client";
import type { TopologyNode, TopologyQueryKindValue, TopologyResult } from "@/features/infrastructure/types";

interface TopologyNodeResponseBody {
  id: string;
  name: string;
  asset_type: string;
  distance: number | null;
  relationship_type: string | null;
  outgoing: boolean | null;
}

interface TopologyResponseBody {
  root_asset_id: string;
  query_kind: TopologyQueryKindValue;
  nodes: TopologyNodeResponseBody[];
}

function toNode(body: TopologyNodeResponseBody): TopologyNode {
  return {
    id: body.id,
    name: body.name,
    assetType: body.asset_type,
    distance: body.distance,
    relationshipType: body.relationship_type,
    outgoing: body.outgoing,
  };
}

export const topologyApi = {
  async get(assetId: string, queryKind: TopologyQueryKindValue, depth?: number): Promise<TopologyResult> {
    const query = new URLSearchParams({ asset_id: assetId, query_kind: queryKind });
    if (depth) query.set("depth", String(depth));
    const body = await apiClient.get<TopologyResponseBody>(`/inventory/topology?${query.toString()}`);
    return { rootAssetId: body.root_asset_id, queryKind: body.query_kind, nodes: body.nodes.map(toNode) };
  },
};
