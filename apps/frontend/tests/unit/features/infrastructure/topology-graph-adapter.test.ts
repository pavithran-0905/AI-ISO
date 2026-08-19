import { describe, expect, it } from "vitest";

import { buildFocusGraph } from "@/features/infrastructure/lib/topology-graph-adapter";
import type { Asset, TopologyResult } from "@/features/infrastructure/types";

const ROOT: Pick<Asset, "id" | "name" | "assetType" | "health"> = {
  id: "root",
  name: "web-01",
  assetType: "web_server",
  health: "healthy",
};

describe("buildFocusGraph", () => {
  it("always includes the root node, marked isRoot", () => {
    const neighbors: TopologyResult = { rootAssetId: "root", queryKind: "neighbors", nodes: [] };
    const graph = buildFocusGraph(ROOT, neighbors, new Map());
    expect(graph.nodes).toEqual([{ id: "root", name: "web-01", assetType: "web_server", health: "healthy", isRoot: true }]);
    expect(graph.edges).toEqual([]);
  });

  it("resolves an outgoing edge (root is the source) from outgoing: true", () => {
    const neighbors: TopologyResult = {
      rootAssetId: "root",
      queryKind: "neighbors",
      nodes: [{ id: "db", name: "db-01", assetType: "database", distance: 1, relationshipType: "depends_on", outgoing: true }],
    };
    const graph = buildFocusGraph(ROOT, neighbors, new Map([["db", "critical"]]));
    expect(graph.edges).toEqual([{ id: "root::depends_on::db", source: "root", target: "db", relationshipType: "depends_on" }]);
    expect(graph.nodes).toContainEqual({ id: "db", name: "db-01", assetType: "database", health: "critical", isRoot: false });
  });

  it("resolves an incoming edge (root is the target) from outgoing: false", () => {
    const neighbors: TopologyResult = {
      rootAssetId: "root",
      queryKind: "neighbors",
      nodes: [{ id: "lb", name: "lb-01", assetType: "load_balancer", distance: 1, relationshipType: "depends_on", outgoing: false }],
    };
    const graph = buildFocusGraph(ROOT, neighbors, new Map());
    expect(graph.edges).toEqual([{ id: "lb::depends_on::root", source: "lb", target: "root", relationshipType: "depends_on" }]);
  });

  it("adds a node with no edge when relationshipType is null", () => {
    const neighbors: TopologyResult = {
      rootAssetId: "root",
      queryKind: "neighbors",
      nodes: [{ id: "orphan", name: "orphan-01", assetType: "custom_asset", distance: null, relationshipType: null, outgoing: null }],
    };
    const graph = buildFocusGraph(ROOT, neighbors, new Map());
    expect(graph.edges).toEqual([]);
    expect(graph.nodes.map((node) => node.id)).toEqual(["root", "orphan"]);
  });

  it("defaults health to null when the neighbor isn't found in the health map", () => {
    const neighbors: TopologyResult = {
      rootAssetId: "root",
      queryKind: "neighbors",
      nodes: [{ id: "db", name: "db-01", assetType: "database", distance: 1, relationshipType: "depends_on", outgoing: true }],
    };
    const graph = buildFocusGraph(ROOT, neighbors, new Map());
    expect(graph.nodes.find((node) => node.id === "db")?.health).toBeNull();
  });

  it("does not duplicate a node that appears more than once in the response", () => {
    const neighbors: TopologyResult = {
      rootAssetId: "root",
      queryKind: "neighbors",
      nodes: [
        { id: "db", name: "db-01", assetType: "database", distance: 1, relationshipType: "depends_on", outgoing: true },
        { id: "db", name: "db-01", assetType: "database", distance: 1, relationshipType: "backed_up_by", outgoing: true },
      ],
    };
    const graph = buildFocusGraph(ROOT, neighbors, new Map());
    expect(graph.nodes.filter((node) => node.id === "db")).toHaveLength(1);
    expect(graph.edges).toHaveLength(2);
  });
});
