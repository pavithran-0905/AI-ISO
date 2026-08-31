import type { Alert } from "@/features/alerting/types";
import type { AutomationJob } from "@/features/automation/types";
import type { Conversation } from "@/features/ai-assistant/types";
import type { Asset } from "@/features/infrastructure/types";
import type { Report } from "@/features/reporting/types";
import type { UserSummary } from "@/features/administration/types";
import type { SearchResult } from "@/features/search/types";

function formatLabel(value: string): string {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function assetToResult(asset: Asset): SearchResult {
  return {
    id: asset.id,
    resultType: "asset",
    title: asset.displayName ?? asset.name,
    description: asset.hostname ?? formatLabel(asset.assetType),
    status: formatLabel(asset.status),
    href: `/infrastructure/assets/${asset.id}`,
  };
}

export function userToResult(user: UserSummary): SearchResult {
  return {
    id: user.id,
    resultType: "user",
    title: user.displayName ?? user.username,
    description: user.email,
    status: formatLabel(user.status),
    href: `/administration/users/${user.id}`,
  };
}

export function alertToResult(alert: Alert): SearchResult {
  return {
    id: alert.id,
    resultType: "alert",
    title: alert.title,
    description: alert.message.length > 80 ? `${alert.message.slice(0, 80)}…` : alert.message,
    status: formatLabel(alert.status),
    href: `/alerting/alerts/${alert.id}`,
  };
}

export function automationToResult(job: AutomationJob): SearchResult {
  return {
    id: job.id,
    resultType: "automation",
    title: job.name,
    description: job.description ?? formatLabel(job.automationType),
    status: formatLabel(job.status),
    href: `/automation/automations/${job.id}`,
  };
}

export function reportToResult(report: Report): SearchResult {
  return {
    id: report.id,
    resultType: "report",
    title: report.name,
    description: report.description ?? formatLabel(report.category),
    status: report.enabled ? "Enabled" : "Disabled",
    href: `/reporting/reports/${report.id}`,
  };
}

/** `href` deep-links to the real, already-established
 * `?conversation=` param on the Assistant workspace
 * (`features/ai-assistant/pages/assistant-workspace-page.tsx`) —
 * never a new route. */
export function conversationToResult(conversation: Conversation): SearchResult {
  return {
    id: conversation.id,
    resultType: "conversation",
    title: conversation.title,
    description: null,
    status: formatLabel(conversation.status),
    href: `/intelligence/assistant?conversation=${conversation.id}`,
  };
}
