/**
 * Types mirroring the real V1 responses this feature consumes,
 * confirmed by direct source inspection — never inferred from a
 * service's name. See `docs/frontend/developer-guide/monitoring.md`
 * for the endpoint each one comes from.
 *
 * Asset types (`Asset`, asset enums, relationships, inventory
 * statistics) moved to `features/infrastructure` (Prompt 011), which
 * now owns all asset-fetching — see that feature's own types and
 * `docs/frontend/developer-guide/infrastructure-inventory.md`
 * "Consolidation" for why. This module keeps only service-topology and
 * platform-event types, which remain genuinely Monitoring's own.
 */

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
