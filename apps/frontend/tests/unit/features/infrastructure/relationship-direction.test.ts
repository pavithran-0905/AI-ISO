import { describe, expect, it } from "vitest";

import { resolveRelationshipNeighbor } from "@/features/infrastructure/lib/relationship-direction";
import type { AssetRelationship } from "@/features/infrastructure/types";

function relationship(overrides: Partial<AssetRelationship>): AssetRelationship {
  return {
    id: "r1",
    organizationId: "org-1",
    sourceAssetId: "a1",
    targetAssetId: "a2",
    relationshipType: "depends_on",
    customLabel: null,
    metadata: {},
    ...overrides,
  };
}

describe("resolveRelationshipNeighbor", () => {
  it("resolves the target as the neighbor, direction outgoing, when the viewed asset is the source", () => {
    const result = resolveRelationshipNeighbor(relationship({ sourceAssetId: "a1", targetAssetId: "a2" }), "a1");
    expect(result).toEqual({ neighborAssetId: "a2", direction: "outgoing" });
  });

  it("resolves the source as the neighbor, direction incoming, when the viewed asset is the target", () => {
    const result = resolveRelationshipNeighbor(relationship({ sourceAssetId: "a1", targetAssetId: "a2" }), "a2");
    expect(result).toEqual({ neighborAssetId: "a1", direction: "incoming" });
  });
});
