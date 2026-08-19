/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection of `services/inventory-service`
 * — enums from `app/models/enums.py`, shapes from `app/schemas/asset.py`,
 * `group.py`, `relationship.py`, `topology.py`, `statistics.py`,
 * `import_export.py`. See `docs/frontend/developer-guide/infrastructure-inventory.md`
 * for the endpoint each one comes from and the security-relevant gaps
 * this typing doesn't paper over.
 *
 * This module supersedes `features/monitoring`'s own narrower,
 * read-only asset types (a strict subset missing `macAddress`/
 * `serialNumber`/`firmwareVersion`/`architecture`/`currentVersion`) —
 * see `docs/frontend/developer-guide/infrastructure-inventory.md`
 * "Consolidation" for why.
 */

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

/** `AssetStatus` — inventory-service-local. */
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

/** `HealthStatus` — inventory-service-local, distinct from
 * `observability-platform-service`'s own topology health vocabulary. */
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

/** `RelationshipType` — inherently directional (`runs_on` means
 * *source* runs on *target*, not the reverse). See `AssetRelationship`'s
 * own docstring on why the raw `sourceAssetId`/`targetAssetId` pair is
 * kept instead of a pre-resolved "neighbor" shape. */
export const RELATIONSHIP_TYPES = [
  "runs_on",
  "hosted_by",
  "connected_to",
  "depends_on",
  "consumes",
  "provides",
  "owns",
  "managed_by",
  "protected_by",
  "replicated_to",
  "backed_up_by",
  "contains",
  "part_of",
  "member_of",
  "communicates_with",
  "custom_relationship",
] as const;
export type RelationshipTypeValue = (typeof RELATIONSHIP_TYPES)[number];

export const GROUP_TYPES = ["static", "dynamic", "rule_based", "location", "application", "environment", "custom"] as const;
export type GroupTypeValue = (typeof GROUP_TYPES)[number];

export const IMPORT_FORMATS = ["csv", "excel", "json", "yaml", "zip"] as const;
export type ImportFormatValue = (typeof IMPORT_FORMATS)[number];

export const EXPORT_FORMATS = ["csv", "excel", "json", "yaml", "pdf", "zip"] as const;
export type ExportFormatValue = (typeof EXPORT_FORMATS)[number];

export const TOPOLOGY_QUERY_KINDS = ["neighbors", "dependencies", "impact"] as const;
export type TopologyQueryKindValue = (typeof TOPOLOGY_QUERY_KINDS)[number];

/** `shared_core.enums.job_status.JobStatus` — 13 values, shared by
 * both export and import jobs. A different, unrelated vocabulary from
 * `features/automation`'s own local 4-value `JobStatusValue`
 * (draft/active/disabled/archived, `AutomationJob.status`) — same
 * name, two different enums, never conflated. */
export const IMPORT_EXPORT_JOB_STATUSES = [
  "registered",
  "scheduled",
  "pending",
  "queued",
  "running",
  "completed",
  "failed",
  "retrying",
  "paused",
  "cancelled",
  "timed_out",
  "expired",
  "archived",
] as const;
export type ImportExportJobStatusValue = (typeof IMPORT_EXPORT_JOB_STATUSES)[number];

/** Non-terminal states worth continuing to poll — the complement is
 * `completed`/`failed`/`cancelled`/`timed_out`/`expired`/`archived`. */
export const ACTIVE_JOB_STATUSES: ReadonlySet<ImportExportJobStatusValue> = new Set([
  "registered",
  "scheduled",
  "pending",
  "queued",
  "running",
  "retrying",
  "paused",
]);

/**
 * `AssetResponse` — `app/schemas/asset.py`. `categoryId`/`classId`/
 * `locationId`/`ownerId` stay raw ids: no category/class/location/owner
 * name-resolution endpoint exists on this service (confirmed absent —
 * see the developer guide). `currentVersion` exists on the response but
 * nothing exposes a way to read a past version or a conflict's other
 * side, so it's shown only as a plain number, never used for
 * optimistic-lock UI this backend can't back.
 */
export interface Asset {
  id: string;
  organizationId: string;
  projectId: string | null;
  name: string;
  displayName: string | null;
  hostname: string | null;
  fqdn: string | null;
  ipAddress: string | null;
  macAddress: string | null;
  serialNumber: string | null;
  vendor: string | null;
  manufacturer: string | null;
  model: string | null;
  firmwareVersion: string | null;
  operatingSystem: string | null;
  architecture: string | null;
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
  currentVersion: number;
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

/** `GET /inventory/search`'s real, confirmed query params — no
 * `health`/`lifecycle_state`/`criticality`/`environment`/`category_id`/
 * `class_id`/`location_id`/`tags` filter exists (confirmed absent by
 * source inspection of the route), so none is offered here as if it
 * were server-side. */
export interface AssetSearchParams {
  organizationId: string;
  query?: string;
  assetType?: AssetTypeValue;
  status?: AssetStatusValue;
  ownerId?: string;
  projectId?: string;
  page?: number;
  pageSize?: number;
  /** `field:asc|desc` — `services/inventory-service`'s own
   * `parse_sort_expression` syntax, passed through verbatim. */
  sort?: string;
}

/** `AssetCreateRequest`. `assetType` has no default — a real choice is
 * required. Every other identity/hardware field is genuinely optional. */
export interface CreateAssetInput {
  organizationId: string;
  projectId?: string;
  name: string;
  displayName?: string;
  hostname?: string;
  fqdn?: string;
  ipAddress?: string;
  macAddress?: string;
  serialNumber?: string;
  vendor?: string;
  manufacturer?: string;
  model?: string;
  firmwareVersion?: string;
  operatingSystem?: string;
  architecture?: string;
  environment?: string;
  assetType: AssetTypeValue;
  categoryId?: string;
  classId?: string;
  locationId?: string;
  ownerId?: string;
  criticality?: CriticalityValue;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

/**
 * `AssetPatchRequest` — the only edit path this feature exposes.
 * `PUT /inventory/assets/{id}` also exists but is a full replace whose
 * schema defaults every omitted field (`status`→`discovered`,
 * `health`→`unknown`, `criticality`→`medium`, ...) rather than leaving
 * it unchanged — the same "PUT status trap" shape found in
 * `automation-service`'s job-update route (Prompt 009). `PATCH` uses
 * `exclude_unset`, a true partial update, so it's the only edit
 * operation built here. Neither route can change `assetType` or `tags`
 * — both are absent from both schemas, confirmed by source inspection.
 */
export interface PatchAssetInput {
  name?: string;
  displayName?: string;
  hostname?: string;
  fqdn?: string;
  ipAddress?: string;
  macAddress?: string;
  serialNumber?: string;
  vendor?: string;
  manufacturer?: string;
  model?: string;
  firmwareVersion?: string;
  operatingSystem?: string;
  architecture?: string;
  environment?: string;
  categoryId?: string;
  classId?: string;
  locationId?: string;
  ownerId?: string;
  status?: AssetStatusValue;
  health?: AssetHealthValue;
  lifecycleState?: LifecycleStateValue;
  criticality?: CriticalityValue;
  metadata?: Record<string, unknown>;
}

/**
 * `AssetRelationshipResponse`. A directed edge, kept raw rather than
 * pre-resolved into a "neighbor" shape — `RelationshipType` values
 * (`runs_on`, `depends_on`, ...) are inherently directional, and
 * `GET /inventory/relationships?asset_id=` returns every edge touching
 * an asset on *either* side (confirmed: the repository queries
 * `source_asset_id = :id OR target_asset_id = :id`). Callers must
 * check which side the asset in view is on — see
 * `lib/relationship-direction.ts`.
 */
export interface AssetRelationship {
  id: string;
  organizationId: string;
  sourceAssetId: string;
  targetAssetId: string;
  relationshipType: RelationshipTypeValue;
  customLabel: string | null;
  metadata: Record<string, unknown>;
}

export interface CreateRelationshipInput {
  organizationId: string;
  sourceAssetId: string;
  targetAssetId: string;
  relationshipType: RelationshipTypeValue;
  customLabel?: string;
}

/** `AssetGroupResponse`. No delete or add/remove-member route exists
 * (confirmed absent — the service methods exist, nothing routes to
 * them), so a group's membership is fixed at creation time in this UI. */
export interface AssetGroup {
  id: string;
  organizationId: string;
  name: string;
  description: string | null;
  groupType: GroupTypeValue;
  rule: Record<string, unknown>;
  memberAssetIds: string[];
}

export interface CreateGroupInput {
  organizationId: string;
  name: string;
  description?: string;
  groupType?: GroupTypeValue;
  memberAssetIds?: string[];
}

/** `TopologyNode` — `GET /inventory/topology`. `assetType` arrives as
 * a plain string on this endpoint specifically (not the `AssetType`
 * enum every other response uses) — kept untyped to match. */
export interface TopologyNode {
  id: string;
  name: string;
  assetType: string;
  distance: number | null;
  relationshipType: string | null;
  outgoing: boolean | null;
}

export interface TopologyResult {
  rootAssetId: string;
  queryKind: TopologyQueryKindValue;
  nodes: TopologyNode[];
}

/** `InventoryStatisticsResponse` — `GET /inventory/statistics`. Every
 * `*Distribution` field is a real server-computed breakdown, never
 * derived client-side from a partial page of results. */
export interface InventoryStatistics {
  totalAssets: number;
  totalRelationships: number;
  typeDistribution: Record<string, number>;
  healthDistribution: Record<string, number>;
  lifecycleDistribution: Record<string, number>;
  osDistribution: Record<string, number>;
  vendorDistribution: Record<string, number>;
  locationDistribution: Record<string, number>;
  computedAt: string;
}

/** `InventoryAnalyticsResponse` — `GET /inventory/analytics`, a
 * superset of statistics. */
export interface InventoryAnalytics extends InventoryStatistics {
  discoverySourceDistribution: Record<string, number>;
  assetsAddedLast30Days: number;
}

/** `ExportRequest`. `status` is a plain string on this one request
 * specifically (confirmed: typed `str | None`, not `AssetStatus`, in
 * the real schema) — passed through as typed here for caller
 * convenience, but the backend itself does not validate it against
 * the enum. */
export interface CreateExportInput {
  organizationId: string;
  targetFormat?: ExportFormatValue;
  assetType?: AssetTypeValue;
  status?: AssetStatusValue;
  tags?: string[];
}

/** `ExportJobResponse`. `downloadUrl` is a presigned link, fetched
 * and opened directly (not routed through `apiClient`) once the job
 * reaches a terminal successful state. */
export interface ExportJob {
  jobId: string;
  status: ImportExportJobStatusValue;
  targetFormat: ExportFormatValue;
  totalRows: number;
  downloadUrl: string | null;
  startedAt: string | null;
  completedAt: string | null;
}

/** `ImportJobResponse`. No `createdAssetIds` field exists on this
 * response despite the backend model tracking them internally for
 * rollback (confirmed absent) — a completed import can be rolled back
 * by job id, but this UI cannot list which specific assets a job
 * created. */
export interface ImportJob {
  jobId: string;
  status: ImportExportJobStatusValue;
  sourceFormat: ImportFormatValue;
  previewOnly: boolean;
  totalRows: number;
  processedRows: number;
  succeededRows: number;
  failedRows: number;
  duplicateRows: number;
  errorReport: Record<string, unknown>[];
  startedAt: string | null;
  completedAt: string | null;
}

export interface CreateImportInput {
  organizationId: string;
  file: File;
  sourceFormat?: ImportFormatValue;
  previewOnly?: boolean;
}

/**
 * Topology graph model (§31) — deliberately a *different* shape from
 * `TopologyNode` above (the raw `GET /inventory/topology` response
 * node). `lib/topology-graph-adapter.ts` is the one place that
 * converts one into the other (§30's "Graph Adapter"), so the renderer
 * never depends on the backend response shape directly. `health` is
 * joined in from `useAllAssets` — the topology endpoint itself carries
 * no health field on any node.
 */
export interface TopologyGraphNode {
  id: string;
  name: string;
  assetType: string;
  health: AssetHealthValue | null;
  isRoot: boolean;
}

/** A synthetic id (`${source}::${relationshipType}::${target}`) — the
 * topology endpoint gives no edge id of its own (unlike
 * `AssetRelationship`, which does, and which
 * `topology-detail-panel.tsx` cross-references for edge metadata when
 * one real relationship matches). */
export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  relationshipType: string;
}

/**
 * Only ever built from `query_kind=neighbors` (always exactly 1 hop —
 * confirmed by source inspection of `app/topology/graph.py`:
 * `get_dependency_graph`/`get_impact_analysis` return a flat,
 * distance-tagged node list with no parent/path linkage at all, so
 * there is no honest way to know which node connects to which beyond
 * the root for `dependencies`/`impact`. Drawing an edge would mean
 * inventing one. Those two query kinds stay a distance-grouped list
 * (`TopologyListView`), never a canvas.
 */
export interface TopologyGraph {
  rootId: string;
  nodes: TopologyGraphNode[];
  edges: TopologyEdge[];
}

/** A client-side *display* toggle over the already-loaded,
 * depth-bounded graph response — never a backend query param.
 * `GET /inventory/topology` accepts none (confirmed absent by source
 * inspection); this only hides/shows nodes already in memory. */
export interface TopologyFilter {
  visibleAssetTypes: ReadonlySet<string> | null;
}

export type TopologySelection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;

/** Exactly one real layout. The graph this feature renders is always
 * root-plus-immediate-neighbors (see `TopologyGraph`'s own docstring)
 * — a shape already fully determined by construction, so a
 * hierarchical/force-directed/left-to-right layout choice would be
 * premature complexity with nothing left to lay out differently. §20
 * explicitly says not to add multiple layouts unless they materially
 * improve usability; here, none would. */
export type TopologyLayoutValue = "radial";
