import type { AssetRelationship } from "@/features/infrastructure/types";

/**
 * `GET /inventory/relationships?asset_id=` returns every edge touching
 * an asset on *either* side (confirmed by source inspection: the
 * repository queries `source_asset_id = :id OR target_asset_id = :id`)
 * — the raw edge doesn't say which side the asset being viewed is on.
 * `RelationshipType` values (`runs_on`, `depends_on`, ...) are
 * inherently directional, so showing the wrong neighbor id or the
 * wrong direction arrow would misstate the relationship. This resolves
 * it once, in one place, rather than each caller re-deriving it (a
 * subtlety `features/monitoring`'s own prior read-only view didn't
 * handle — it always linked to `targetAssetId`, correct only when the
 * viewed asset happened to be the source).
 */
export function resolveRelationshipNeighbor(
  relationship: AssetRelationship,
  viewedAssetId: string,
): { neighborAssetId: string; direction: "outgoing" | "incoming" } {
  if (relationship.sourceAssetId === viewedAssetId) {
    return { neighborAssetId: relationship.targetAssetId, direction: "outgoing" };
  }
  return { neighborAssetId: relationship.sourceAssetId, direction: "incoming" };
}
