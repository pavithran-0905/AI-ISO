/**
 * `services/inventory-service/app/api/asset.py` + `search.py` —
 * confirmed by source inspection. `GET /inventory/assets` lists an
 * org's complete asset set with no filter/sort/pagination at all (used
 * only where a genuinely unbounded read makes sense, e.g. populating a
 * relationship-target picker) — `GET /inventory/search` is the real,
 * server-side paginated/filtered/sorted/searched list every other view
 * uses.
 */

import { apiClient } from "@/api/client";
import type {
  Asset,
  AssetPagination,
  AssetSearchParams,
  AssetSearchResult,
  AssetStatusValue,
  AssetTypeValue,
  CreateAssetInput,
  CriticalityValue,
  AssetHealthValue,
  LifecycleStateValue,
  PatchAssetInput,
} from "@/features/infrastructure/types";

export interface AssetResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  display_name: string | null;
  hostname: string | null;
  fqdn: string | null;
  ip_address: string | null;
  mac_address: string | null;
  serial_number: string | null;
  vendor: string | null;
  manufacturer: string | null;
  model: string | null;
  firmware_version: string | null;
  operating_system: string | null;
  architecture: string | null;
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
  current_version: number;
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

export function toAsset(body: AssetResponseBody): Asset {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    name: body.name,
    displayName: body.display_name,
    hostname: body.hostname,
    fqdn: body.fqdn,
    ipAddress: body.ip_address,
    macAddress: body.mac_address,
    serialNumber: body.serial_number,
    vendor: body.vendor,
    manufacturer: body.manufacturer,
    model: body.model,
    firmwareVersion: body.firmware_version,
    operatingSystem: body.operating_system,
    architecture: body.architecture,
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
    currentVersion: body.current_version,
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

export const assetsApi = {
  /** Unbounded — only for callers that genuinely need the complete set
   * (e.g. a relationship-target picker), never a primary list view. */
  async listAll(organizationId: string): Promise<Asset[]> {
    const body = await apiClient.get<AssetResponseBody[]>(
      `/inventory/assets?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toAsset);
  },

  async search(params: AssetSearchParams): Promise<AssetSearchResult> {
    const query = new URLSearchParams({ organization_id: params.organizationId });
    if (params.query) query.set("q", params.query);
    if (params.assetType) query.set("asset_type", params.assetType);
    if (params.status) query.set("status", params.status);
    if (params.ownerId) query.set("owner_id", params.ownerId);
    if (params.projectId) query.set("project_id", params.projectId);
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

  async create(input: CreateAssetInput): Promise<Asset> {
    const body = await apiClient.post<AssetResponseBody>("/inventory/assets", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      name: input.name,
      display_name: input.displayName,
      hostname: input.hostname,
      fqdn: input.fqdn,
      ip_address: input.ipAddress,
      mac_address: input.macAddress,
      serial_number: input.serialNumber,
      vendor: input.vendor,
      manufacturer: input.manufacturer,
      model: input.model,
      firmware_version: input.firmwareVersion,
      operating_system: input.operatingSystem,
      architecture: input.architecture,
      environment: input.environment,
      asset_type: input.assetType,
      category_id: input.categoryId,
      class_id: input.classId,
      location_id: input.locationId,
      owner_id: input.ownerId,
      criticality: input.criticality,
      metadata: input.metadata ?? {},
      tags: input.tags ?? [],
    });
    return toAsset(body);
  },

  /** `PATCH` only — see `PatchAssetInput`'s own docstring for why
   * `PUT` is never used here. */
  async patch(id: string, input: PatchAssetInput): Promise<Asset> {
    const body = await apiClient.patch<AssetResponseBody>(`/inventory/assets/${encodeURIComponent(id)}`, {
      name: input.name,
      display_name: input.displayName,
      hostname: input.hostname,
      fqdn: input.fqdn,
      ip_address: input.ipAddress,
      mac_address: input.macAddress,
      serial_number: input.serialNumber,
      vendor: input.vendor,
      manufacturer: input.manufacturer,
      model: input.model,
      firmware_version: input.firmwareVersion,
      operating_system: input.operatingSystem,
      architecture: input.architecture,
      environment: input.environment,
      category_id: input.categoryId,
      class_id: input.classId,
      location_id: input.locationId,
      owner_id: input.ownerId,
      status: input.status,
      health: input.health,
      lifecycle_state: input.lifecycleState,
      criticality: input.criticality,
      metadata: input.metadata,
    });
    return toAsset(body);
  },

  /** A real soft delete (`AssetStatus.DELETED` + `is_active=False`
   * server-side) — the asset stops appearing in every list/search/get
   * call afterward; there is no restore endpoint. */
  async remove(id: string): Promise<void> {
    await apiClient.delete<{ success: boolean }>(`/inventory/assets/${encodeURIComponent(id)}`);
  },
};
