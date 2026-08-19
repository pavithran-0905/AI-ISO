/**
 * `services/inventory-service/app/api/group.py` — confirmed by source
 * inspection. No delete or add/remove-member route exists — see
 * `AssetGroup`'s own docstring.
 */

import { apiClient } from "@/api/client";
import { toAsset, type AssetResponseBody } from "@/features/infrastructure/api/assets-api";
import type { Asset, AssetGroup, CreateGroupInput, GroupTypeValue } from "@/features/infrastructure/types";

interface AssetGroupResponseBody {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  group_type: GroupTypeValue;
  rule: Record<string, unknown>;
  member_asset_ids: string[];
}

function toGroup(body: AssetGroupResponseBody): AssetGroup {
  return {
    id: body.id,
    organizationId: body.organization_id,
    name: body.name,
    description: body.description,
    groupType: body.group_type,
    rule: body.rule,
    memberAssetIds: body.member_asset_ids,
  };
}

export const groupsApi = {
  async list(organizationId: string): Promise<AssetGroup[]> {
    const body = await apiClient.get<AssetGroupResponseBody[]>(
      `/inventory/groups?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toGroup);
  },

  async create(input: CreateGroupInput): Promise<AssetGroup> {
    const body = await apiClient.post<AssetGroupResponseBody>("/inventory/groups", {
      organization_id: input.organizationId,
      name: input.name,
      description: input.description,
      group_type: input.groupType ?? "static",
      member_asset_ids: input.memberAssetIds ?? [],
    });
    return toGroup(body);
  },

  /** Live-resolved for dynamic/rule-based groups, stored for every
   * other group type — the backend's own distinction, not this
   * feature's. */
  async members(groupId: string): Promise<Asset[]> {
    const body = await apiClient.get<AssetResponseBody[]>(
      `/inventory/groups/${encodeURIComponent(groupId)}/members`,
    );
    return body.map(toAsset);
  },
};
