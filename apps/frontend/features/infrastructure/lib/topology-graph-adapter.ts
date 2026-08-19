import type { Asset, TopologyEdge, TopologyGraph, TopologyGraphNode, TopologyResult } from "@/features/infrastructure/types";

/**
 * `GET /inventory/topology?query_kind=neighbors` → `TopologyGraph`
 * (§30 "Graph Adapter"). Only `neighbors` is ever passed in here:
 * it's the one query kind that carries real per-edge
 * `relationshipType`/`outgoing` (confirmed by source inspection —
 * `dependencies`/`impact` never populate either field). `health` comes
 * from a separate join against `useAllAssets`, not from the topology
 * response itself, which has no health field on any node.
 */
export function buildFocusGraph(
  root: Pick<Asset, "id" | "name" | "assetType" | "health">,
  neighbors: TopologyResult,
  healthById: ReadonlyMap<string, Asset["health"]>,
): TopologyGraph {
  const nodes: TopologyGraphNode[] = [
    { id: root.id, name: root.name, assetType: root.assetType, health: root.health, isRoot: true },
  ];
  const edges: TopologyEdge[] = [];
  const seenNodeIds = new Set<string>([root.id]);

  for (const node of neighbors.nodes) {
    if (!seenNodeIds.has(node.id)) {
      seenNodeIds.add(node.id);
      nodes.push({
        id: node.id,
        name: node.name,
        assetType: node.assetType,
        health: healthById.get(node.id) ?? null,
        isRoot: false,
      });
    }

    if (node.relationshipType) {
      // `outgoing` is real but nullable on the wire; a neighbor row
      // with a relationship type always has a direction in practice
      // (confirmed: `get_neighbors`'s own Cypher always returns
      // `startNode(r).id = a.id AS outgoing` alongside `type(r)`) —
      // the `?? true` only guards TypeScript's `boolean | null`, it
      // never masks a real unknown-direction case.
      const isOutgoingFromRoot = node.outgoing ?? true;
      const source = isOutgoingFromRoot ? root.id : node.id;
      const target = isOutgoingFromRoot ? node.id : root.id;
      edges.push({
        id: `${source}::${node.relationshipType}::${target}`,
        source,
        target,
        relationshipType: node.relationshipType,
      });
    }
  }

  return { rootId: root.id, nodes, edges };
}
