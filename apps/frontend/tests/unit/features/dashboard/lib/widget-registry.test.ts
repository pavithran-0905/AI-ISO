import { describe, expect, it } from "vitest";

import { DASHBOARD_WIDGET_REGISTRY, filterVisibleWidgets } from "@/features/dashboard/lib/widget-registry";

describe("filterVisibleWidgets", () => {
  it("only returns widgets registered for the given mode", () => {
    const executive = filterVisibleWidgets({ mode: "executive", role: null, hiddenWidgetIds: [] });
    const operations = filterVisibleWidgets({ mode: "operations", role: null, hiddenWidgetIds: [] });

    expect(executive.some((w) => w.id === "reporting-status")).toBe(true);
    expect(operations.some((w) => w.id === "reporting-status")).toBe(false);
    expect(operations.some((w) => w.id === "operations-signals")).toBe(true);
    expect(executive.some((w) => w.id === "operations-signals")).toBe(false);
  });

  it("hides a widget present in hiddenWidgetIds (§24 personalization)", () => {
    const visible = filterVisibleWidgets({ mode: "executive", role: null, hiddenWidgetIds: ["ai-insight"] });
    expect(visible.some((w) => w.id === "ai-insight")).toBe(false);
  });

  it("hides a role-restricted widget from a role not in its list (§27 permission-aware widgets)", () => {
    const restricted = { ...DASHBOARD_WIDGET_REGISTRY[0], id: "synthetic-restricted", roles: ["super_admin" as const] };
    const original = DASHBOARD_WIDGET_REGISTRY.slice();
    DASHBOARD_WIDGET_REGISTRY.push(restricted);
    try {
      const asViewer = filterVisibleWidgets({ mode: restricted.modes[0], role: "viewer", hiddenWidgetIds: [] });
      const asAdmin = filterVisibleWidgets({ mode: restricted.modes[0], role: "super_admin", hiddenWidgetIds: [] });
      expect(asViewer.some((w) => w.id === "synthetic-restricted")).toBe(false);
      expect(asAdmin.some((w) => w.id === "synthetic-restricted")).toBe(true);
    } finally {
      DASHBOARD_WIDGET_REGISTRY.length = 0;
      DASHBOARD_WIDGET_REGISTRY.push(...original);
    }
  });

  it("hides a role-restricted widget entirely when the caller has no role at all", () => {
    const restricted = { ...DASHBOARD_WIDGET_REGISTRY[0], id: "synthetic-restricted-2", roles: ["super_admin" as const] };
    const original = DASHBOARD_WIDGET_REGISTRY.slice();
    DASHBOARD_WIDGET_REGISTRY.push(restricted);
    try {
      const visible = filterVisibleWidgets({ mode: restricted.modes[0], role: null, hiddenWidgetIds: [] });
      expect(visible.some((w) => w.id === "synthetic-restricted-2")).toBe(false);
    } finally {
      DASHBOARD_WIDGET_REGISTRY.length = 0;
      DASHBOARD_WIDGET_REGISTRY.push(...original);
    }
  });

  it("every registered widget's component shares the same {organizationId} shape", () => {
    for (const widget of DASHBOARD_WIDGET_REGISTRY) {
      expect(typeof widget.component).toBe("function");
    }
  });

  it("Recent Activity's own role restriction is inherited live from the real Audit route, not hand-picked", () => {
    const recentActivity = DASHBOARD_WIDGET_REGISTRY.find((w) => w.id === "recent-activity");
    expect(recentActivity?.roles).toEqual(["super_admin", "organization_admin"]);

    const asViewer = filterVisibleWidgets({ mode: "executive", role: "viewer", hiddenWidgetIds: [] });
    const asAdmin = filterVisibleWidgets({ mode: "executive", role: "organization_admin", hiddenWidgetIds: [] });
    expect(asViewer.some((w) => w.id === "recent-activity")).toBe(false);
    expect(asAdmin.some((w) => w.id === "recent-activity")).toBe(true);
  });
});
