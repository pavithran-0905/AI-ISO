import type { ComponentType } from "react";

import type { Role } from "@/auth/types";
import { AiInsightWidget } from "@/features/dashboard/components/ai-insight-widget";
import { InfrastructureOverviewWidget } from "@/features/dashboard/components/infrastructure-overview-widget";
import { NotificationSummaryWidget } from "@/features/dashboard/components/notification-summary-widget";
import { OperationsSignalsWidget } from "@/features/dashboard/components/operations-signals-widget";
import { ReportingStatusWidget } from "@/features/dashboard/components/reporting-status-widget";
import { RecentActivityTimeline } from "@/features/operations/components/recent-activity-timeline";
import { getRouteById } from "@/lib/route-registry";

export const DASHBOARD_MODES = ["executive", "operations"] as const;
export type DashboardModeValue = (typeof DASHBOARD_MODES)[number];

export interface DashboardWidgetDefinition {
  id: string;
  title: string;
  modes: readonly DashboardModeValue[];
  /** `null` = every authenticated user. Sourced from the route this
   * widget's own action links into (§47/§27), never a second,
   * hand-picked restriction — if that route ever gains a role
   * restriction, this widget picks it up automatically rather than
   * silently drifting out of sync with it. */
  roles: Role[] | null;
  defaultVisible: boolean;
  component: ComponentType<{ organizationId: string }>;
}

/**
 * §26's typed widget registry — every *optional*, user-toggleable
 * widget (§24). The six foundational sections (Executive Summary,
 * Asset Health, Active Alerts, Automation Status, System Status, Quick
 * Access) are load-bearing for both dashboard modes and intentionally
 * NOT part of this list — see `features/dashboard/pages/dashboard-page.tsx`'s
 * own comment for why forcing them through a hideable registry would
 * be a regression, not an improvement. Every `component` here takes
 * the exact same `{ organizationId }` shape so the page can render this
 * list generically, with no per-widget special-casing.
 */
export const DASHBOARD_WIDGET_REGISTRY: DashboardWidgetDefinition[] = [
  {
    id: "recent-activity",
    title: "Recent activity",
    modes: DASHBOARD_MODES,
    roles: getRouteById("audit")?.roles ?? null,
    defaultVisible: true,
    component: RecentActivityTimeline,
  },
  {
    id: "infrastructure-overview",
    title: "Infrastructure",
    modes: DASHBOARD_MODES,
    roles: getRouteById("infrastructure")?.roles ?? null,
    defaultVisible: true,
    component: InfrastructureOverviewWidget,
  },
  {
    id: "notification-summary",
    title: "Notifications",
    modes: DASHBOARD_MODES,
    roles: getRouteById("notifications")?.roles ?? null,
    defaultVisible: true,
    component: NotificationSummaryWidget,
  },
  {
    id: "reporting-status",
    title: "Reporting",
    modes: ["executive"],
    roles: getRouteById("reporting")?.roles ?? null,
    defaultVisible: true,
    component: ReportingStatusWidget,
  },
  {
    id: "ai-insight",
    title: "AI Insight",
    modes: ["executive"],
    roles: getRouteById("intelligence")?.roles ?? null,
    defaultVisible: true,
    component: AiInsightWidget,
  },
  {
    id: "operations-signals",
    title: "Operations Workspace",
    modes: ["operations"],
    roles: getRouteById("operations-workspace")?.roles ?? null,
    defaultVisible: true,
    component: OperationsSignalsWidget,
  },
];

/**
 * The pure filtering rule §27 (permission-aware widgets) and §5 (mode)
 * both describe — extracted so it's directly unit-testable with
 * synthetic roles/modes, independent of whether any *currently*
 * registered widget's linked route happens to carry a real role
 * restriction (today, none does; see each entry's own `roles` comment
 * above).
 */
export function filterVisibleWidgets({
  mode,
  role,
  hiddenWidgetIds,
}: {
  mode: DashboardModeValue;
  role: Role | null;
  hiddenWidgetIds: readonly string[];
}): DashboardWidgetDefinition[] {
  return DASHBOARD_WIDGET_REGISTRY.filter((widget) => {
    if (!widget.modes.includes(mode)) return false;
    if (widget.roles !== null && (role === null || !widget.roles.includes(role))) return false;
    if (hiddenWidgetIds.includes(widget.id)) return false;
    return true;
  });
}
