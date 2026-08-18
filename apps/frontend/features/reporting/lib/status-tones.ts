import type { StatusTone } from "@/components/feedback/status-badge";
import type {
  ArchiveStatusValue,
  DistributionStatusValue,
  ReportExecutionStatusValue,
  TemplateStatusValue,
} from "@/features/reporting/types";

/** Each of this feature's status enums is independent — a generation's
 * `ReportExecutionStatusValue` has nothing to do with a template's own
 * `TemplateStatusValue` — so each gets its own tone map rather than one
 * shared vocabulary, matching `@/lib/status`'s own reuse-the-palette,
 * don't-conflate-the-meaning approach. */
export const EXECUTION_STATUS_TONE: Record<ReportExecutionStatusValue, StatusTone> = {
  pending: "pending",
  running: "running",
  succeeded: "success",
  failed: "danger",
  cancelled: "neutral",
};

export const TEMPLATE_STATUS_TONE: Record<TemplateStatusValue, StatusTone> = {
  draft: "neutral",
  approved: "success",
  archived: "neutral",
};

export const DISTRIBUTION_STATUS_TONE: Record<DistributionStatusValue, StatusTone> = {
  pending: "pending",
  delivered: "success",
  failed: "danger",
  expired: "neutral",
};

export const ARCHIVE_STATUS_TONE: Record<ArchiveStatusValue, StatusTone> = {
  active: "success",
  restored: "info",
  purged: "neutral",
};
