/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection — never inferred from a
 * service's name. See `docs/frontend/developer-guide/monitoring.md`
 * for the endpoint each one comes from.
 */

/** `services/inventory-service/app/models/enums.py` — 44 values,
 * verbatim. */
export const ASSET_TYPES = [
  "physical_server",
  "virtual_machine",
  "bare_metal",
  "hypervisor",
  "container",
  "container_image",
  "kubernetes_cluster",
  "namespace",
  "pod",
  "deployment",
  "stateful_set",
  "daemon_set",
  "service",
  "ingress",
  "persistent_volume",
  "storage_system",
  "san",
  "nas",
  "object_storage",
  "switch",
  "router",
  "firewall",
  "load_balancer",
  "wireless_controller",
  "industrial_controller",
  "plc",
  "rtu",
  "dcs_controller",
  "opc_ua_server",
  "opc_ua_device",
  "iot_device",
  "cloud_account",
  "cloud_region",
  "cloud_resource",
  "application",
  "microservice",
  "database",
  "middleware",
  "message_broker",
  "web_server",
  "api_gateway",
  "monitoring_agent",
  "automation_agent",
  "validation_agent",
  "custom_asset",
] as const;
export type AssetTypeValue = (typeof ASSET_TYPES)[number];

/** `AssetStatus` — inventory-service-local (distinct from the unused
 * `shared_core.enums.asset_status` — see developer guide). */
export const ASSET_STATUSES = [
  "discovered",
  "registered",
  "managed",
  "unmanaged",
  "provisioning",
  "maintenance",
  "retired",
  "archived",
  "deleted",
] as const;
export type AssetStatusValue = (typeof ASSET_STATUSES)[number];

/** `HealthStatus` — inventory-service-local. Distinct from
 * `shared_core.enums.health_status.HealthStatus` (used by
 * api-gateway/monitoring-service) despite the identical name — same
 * word, different enum, different values. Never conflate the two. */
export const ASSET_HEALTH_STATUSES = ["healthy", "warning", "critical", "unknown", "offline", "unreachable"] as const;
export type AssetHealthValue = (typeof ASSET_HEALTH_STATUSES)[number];

export const LIFECYCLE_STATES = [
  "planned",
  "provisioning",
  "operational",
  "maintenance",
  "retired",
  "disposed",
  "archived",
] as const;
export type LifecycleStateValue = (typeof LIFECYCLE_STATES)[number];

export const CRITICALITY_LEVELS = ["low", "medium", "high", "critical"] as const;
export type CriticalityValue = (typeof CRITICALITY_LEVELS)[number];

/** `AssetResponse` — `services/inventory-service/app/schemas/asset.py`.
 * `category_id`/`class_id`/`location_id`/`ownerId` stay raw ids: no
 * category/class/location lookup endpoint exists on this service (see
 * the developer guide's Backend V1 limitations note). */
export interface Asset {
  id: string;
  organizationId: string;
  projectId: string | null;
  name: string;
  displayName: string | null;
  hostname: string | null;
  fqdn: string | null;
  ipAddress: string | null;
  vendor: string | null;
  manufacturer: string | null;
  model: string | null;
  operatingSystem: string | null;
  environment: string | null;
  assetType: AssetTypeValue;
  categoryId: string | null;
  classId: string | null;
  locationId: string | null;
  ownerId: string | null;
  status: AssetStatusValue;
  health: AssetHealthValue;
  lifecycleState: LifecycleStateValue;
  criticality: CriticalityValue;
  metadata: Record<string, unknown>;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface AssetPagination {
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
}

export interface AssetSearchResult {
  items: Asset[];
  pagination: AssetPagination;
}

export interface AssetSearchParams {
  organizationId: string;
  query?: string;
  assetType?: AssetTypeValue;
  status?: AssetStatusValue;
  page?: number;
  pageSize?: number;
  /** `field:asc|desc` — `services/inventory-service`'s own
   * `parse_sort_expression` syntax, passed through verbatim. */
  sort?: string;
}

/** `InventoryStatisticsResponse` — `GET /inventory/statistics`. Only
 * the fields this feature actually renders. */
export interface InventoryStatistics {
  totalAssets: number;
  healthDistribution: Record<string, number>;
}

/** `AssetRelationshipResponse` — `GET /inventory/relationships`. */
export interface AssetRelationship {
  id: string;
  sourceAssetId: string;
  targetAssetId: string;
  relationshipType: string;
  customLabel: string | null;
}

/** `NodeHealth` — `services/observability-platform-service/app/models/enums.py`.
 * 4 values — distinct from inventory's `HealthStatus` (6) and
 * api-gateway's `HealthState` (6, from `shared_core`). Three different
 * "health" vocabularies across three services; never conflated. */
export const SERVICE_NODE_HEALTH_STATES = ["healthy", "degraded", "unhealthy", "unknown"] as const;
export type ServiceNodeHealthValue = (typeof SERVICE_NODE_HEALTH_STATES)[number];

/** `TopologyNodeResponse` — `GET /observability/topology`. */
export interface ServiceHealthNode {
  serviceName: string;
  health: ServiceNodeHealthValue;
  fanIn: number;
  fanOut: number;
  criticality: number;
  inCycle: boolean;
}

/** `EventKind` — `services/observability-platform-service/app/models/enums.py`. */
export const EVENT_KINDS = [
  "platform",
  "infrastructure",
  "application",
  "deployment",
  "configuration",
  "security",
  "scaling",
  "incident",
] as const;
export type EventKindValue = (typeof EVENT_KINDS)[number];

/** `EventSeverity` — same file, 5 values, ordered least→most severe. */
export const EVENT_SEVERITIES = ["info", "warning", "minor", "major", "critical"] as const;
export type EventSeverityValue = (typeof EVENT_SEVERITIES)[number];

/** `ObservabilityEventResponse` — `GET /observability/events`. No
 * asset-id reference field exists — correlation to a specific asset
 * isn't possible from this endpoint (see the developer guide). */
export interface ObservabilityEvent {
  id: string;
  eventKind: EventKindValue;
  severity: EventSeverityValue;
  title: string;
  occurredAt: string;
  endedAt: string | null;
  serviceName: string | null;
}
