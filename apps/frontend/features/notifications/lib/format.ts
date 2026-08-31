import type { StatusTone } from "@/components/feedback/status-badge";
import type { NotificationCategoryValue, NotificationPriorityValue, NotificationStatusValue } from "@/features/notifications/types";

export function formatLabel(value: string): string {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Reuses the design system's existing semantic tones (§14: "do not
 * create a second severity model") — mapped from the real
 * `NotificationStatus` lifecycle, not a frontend-invented read/unread
 * binary. */
export const STATUS_TONES: Record<NotificationStatusValue, StatusTone> = {
  created: "neutral",
  queued: "pending",
  sending: "pending",
  sent: "info",
  delivered: "info",
  read: "success",
  acknowledged: "success",
  failed: "danger",
  expired: "neutral",
  cancelled: "neutral",
};

export const PRIORITY_TONES: Record<NotificationPriorityValue, StatusTone> = {
  critical: "danger",
  high: "warning",
  normal: "info",
  low: "neutral",
  background: "neutral",
};

/** "Important" (§4's IA) is not a real backend field — it's this
 * feature's own client-side view over the real `priority` field,
 * documented as such everywhere it appears. */
export function isImportant(priority: NotificationPriorityValue): boolean {
  return priority === "critical" || priority === "high";
}

export function categoryLabel(category: NotificationCategoryValue): string {
  return formatLabel(category);
}
