/**
 * `services/inventory-service` — confirmed by source inspection.
 * `GET /inventory/search` (paginated/filtered/sorted/searched, all
 * server-side — `app/api/search.py`), `GET /inventory/assets/{id}`,
 * `GET /inventory/statistics`, `GET /inventory/relationships`
 * (`app/api/relationship.py`).
 */

import { apiClient } from "@/api/client";
import type {
  Asset,
  AssetHealthValue,
  AssetPagination,
  AssetRelationship,
  AssetSearchParams,
  AssetSearchResult,
  AssetStatusValue,
  AssetTypeValue,
  InventoryStatistics,
  LifecycleStateValue,
  CriticalityValue,
} from "@/features/monitoring/types";

interface AssetResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  display_name: string | null;
  hostname: string | null;
  fqdn: string | null;
  ip_address: string | null;
  vendor: string | null;
  manufacturer: string | null;
  model: string | null;
  operating_system: string | null;
  environment: string | null;
  asset_type: AssetTypeValue;
  category_id: string | null;
  class_id: string | null;
  location_id: string | null;
  owner_id: string | null;
  status: AssetStatusValue;
  health: AssetHealthValue;
  lifecycle_state: LifecycleStateValue;
  criticality: CriticalityValue;
  metadata: Record<string, unknown>;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface PaginationMetadataResponseBody {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

interface AssetSearchResponseBody {
  items: AssetResponseBody[];
  pagination: PaginationMetadataResponseBody;
}

interface InventoryStatisticsResponseBody {
  total_assets: number;
  health_distribution: Record<string, number>;
}

interface AssetRelationshipResponseBody {
  id: string;
  source_asset_id: string;
  target_asset_id: string;
  relationship_type: string;
  custom_label: string | null;
}

function toAsset(body: AssetResponseBody): Asset {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    name: body.name,
    displayName: body.display_name,
    hostname: body.hostname,
    fqdn: body.fqdn,
    ipAddress: body.ip_address,
    vendor: body.vendor,
    manufacturer: body.manufacturer,
    model: body.model,
    operatingSystem: body.operating_system,
    environment: body.environment,
    assetType: body.asset_type,
    categoryId: body.category_id,
    classId: body.class_id,
    locationId: body.location_id,
    ownerId: body.owner_id,
    status: body.status,
    health: body.health,
    lifecycleState: body.lifecycle_state,
    criticality: body.criticality,
    metadata: body.metadata,
    tags: body.tags,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

function toPagination(body: PaginationMetadataResponseBody): AssetPagination {
  return {
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
    totalPages: body.total_pages,
    hasNext: body.has_next,
    hasPrevious: body.has_previous,
  };
}

function toRelationship(body: AssetRelationshipResponseBody): AssetRelationship {
  return {
    id: body.id,
    sourceAssetId: body.source_asset_id,
    targetAssetId: body.target_asset_id,
    relationshipType: body.relationship_type,
    customLabel: body.custom_label,
  };
}

export const assetsApi = {
  async search(params: AssetSearchParams): Promise<AssetSearchResult> {
    const query = new URLSearchParams({ organization_id: params.organizationId });
    if (params.query) query.set("q", params.query);
    if (params.assetType) query.set("asset_type", params.assetType);
    if (params.status) query.set("status", params.status);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    if (params.sort) query.set("sort", params.sort);

    const body = await apiClient.get<AssetSearchResponseBody>(`/inventory/search?${query.toString()}`);
    return { items: body.items.map(toAsset), pagination: toPagination(body.pagination) };
  },

  async getById(id: string): Promise<Asset> {
    const body = await apiClient.get<AssetResponseBody>(`/inventory/assets/${encodeURIComponent(id)}`);
    return toAsset(body);
  },

  async fetchStatistics(organizationId: string): Promise<InventoryStatistics> {
    const body = await apiClient.get<InventoryStatisticsResponseBody>(
      `/inventory/statistics?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return { totalAssets: body.total_assets, healthDistribution: body.health_distribution };
  },

  async fetchRelationships(assetId: string): Promise<AssetRelationship[]> {
    const body = await apiClient.get<AssetRelationshipResponseBody[]>(
      `/inventory/relationships?asset_id=${encodeURIComponent(assetId)}`,
    );
    return body.map(toRelationship);
  },
};
