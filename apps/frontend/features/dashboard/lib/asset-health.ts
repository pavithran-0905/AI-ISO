import type { StatusTone } from "@/components/feedback/status-badge";
import { ASSET_HEALTH_STATUSES, type AssetHealthValue } from "@/features/infrastructure/types";
import { ASSET_HEALTH_TO_STATUS } from "@/features/infrastructure/lib/status-maps";
import { resolveStatus, type StatusState } from "@/lib/status";

export interface HealthSegment {
  key: AssetHealthValue;
  label: string;
  value: number;
  tone: StatusTone;
}

/**
 * `InventoryStatistics.healthDistribution` (`GET /inventory/statistics`)
 * → one segment per real `AssetHealthValue`, tone-mapped through the
 * same `ASSET_HEALTH_TO_STATUS` table Infrastructure's own asset table
 * already uses (Prompt 018) — never a second health→color mapping.
 * Kept in taxonomy order so the legend's order is stable across
 * renders, not re-sorted by count.
 */
export function buildHealthSegments(distribution: Record<string, number>): HealthSegment[] {
  return ASSET_HEALTH_STATUSES.map((health) => {
    const definition = resolveStatus(ASSET_HEALTH_TO_STATUS[health]);
    return { key: health, label: definition.label, value: distribution[health] ?? 0, tone: definition.tone };
  });
}

/** critical/unreachable outrank warning/offline/unknown, which outrank
 * a clean "healthy" — worst-real-tier-present, never an average. */
const CRITICAL_HEALTH: readonly AssetHealthValue[] = ["critical", "unreachable"];
const WARNING_HEALTH: readonly AssetHealthValue[] = ["warning", "offline", "unknown"];

/**
 * The Executive Header's own platform-health badge (§6) — collapsed to
 * the three-tier `Healthy`/`Warning`/`Critical` vocabulary §6 itself
 * asks for, computed only from real counts. Returns `null` when there
 * is no asset data to summarize at all (an empty/unloaded organization
 * gets no badge, never a fabricated "Healthy") — §6: "Do not fabricate
 * platform health."
 */
export function computePlatformHealthTier(distribution: Record<string, number> | undefined): StatusState | null {
  if (!distribution) return null;
  const total = Object.values(distribution).reduce((sum, count) => sum + count, 0);
  if (total === 0) return null;
  if (CRITICAL_HEALTH.some((health) => (distribution[health] ?? 0) > 0)) return "critical";
  if (WARNING_HEALTH.some((health) => (distribution[health] ?? 0) > 0)) return "warning";
  return "healthy";
}
