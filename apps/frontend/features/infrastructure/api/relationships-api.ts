/**
 * `services/inventory-service/app/api/relationship.py` — confirmed by
 * source inspection.
 */

import { apiClient } from "@/api/client";
import type { AssetRelationship, CreateRelationshipInput, RelationshipTypeValue } from "@/features/infrastructure/types";

interface AssetRelationshipResponseBody {
  id: string;
  organization_id: string;
  source_asset_id: string;
  target_asset_id: string;
  relationship_type: RelationshipTypeValue;
  custom_label: string | null;
  metadata: Record<string, unknown>;
}

function toRelationship(body: AssetRelationshipResponseBody): AssetRelationship {
  return {
    id: body.id,
    organizationId: body.organization_id,
    sourceAssetId: body.source_asset_id,
    targetAssetId: body.target_asset_id,
    relationshipType: body.relationship_type,
    customLabel: body.custom_label,
    metadata: body.metadata,
  };
}

export const relationshipsApi = {
  /** Every edge touching `assetId` on either side — see
   * `AssetRelationship`'s own docstring on why the raw pair is kept
   * rather than pre-resolved. */
  async listForAsset(assetId: string): Promise<AssetRelationship[]> {
    const body = await apiClient.get<AssetRelationshipResponseBody[]>(
      `/inventory/relationships?asset_id=${encodeURIComponent(assetId)}`,
    );
    return body.map(toRelationship);
  },

  async create(input: CreateRelationshipInput): Promise<AssetRelationship> {
    const body = await apiClient.post<AssetRelationshipResponseBody>("/inventory/relationships", {
      organization_id: input.organizationId,
      source_asset_id: input.sourceAssetId,
      target_asset_id: input.targetAssetId,
      relationship_type: input.relationshipType,
      custom_label: input.customLabel,
    });
    return toRelationship(body);
  },

  async remove(relationshipId: string): Promise<void> {
    await apiClient.delete<{ success: boolean }>(`/inventory/relationships/${encodeURIComponent(relationshipId)}`);
  },
};
