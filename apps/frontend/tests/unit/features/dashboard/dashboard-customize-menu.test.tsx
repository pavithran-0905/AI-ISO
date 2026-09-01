import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DashboardCustomizeMenu } from "@/features/dashboard/components/dashboard-customize-menu";
import { DASHBOARD_WIDGET_REGISTRY } from "@/features/dashboard/lib/widget-registry";
import { useDashboardPreferencesStore } from "@/state/dashboard-preferences-store";

describe("DashboardCustomizeMenu", () => {
  afterEach(() => {
    cleanup();
    useDashboardPreferencesStore.setState({ preferredMode: "executive", hiddenWidgetIds: [] });
  });

  it("lists every optional widget as a checked-by-default checkbox once opened", () => {
    render(<DashboardCustomizeMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Customize dashboard" }));

    for (const widget of DASHBOARD_WIDGET_REGISTRY) {
      expect(screen.getByRole("checkbox", { name: widget.title })).toBeChecked();
    }
  });

  it("unchecking a widget persists it to hiddenWidgetIds", () => {
    render(<DashboardCustomizeMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Customize dashboard" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "AI Insight" }));

    expect(useDashboardPreferencesStore.getState().hiddenWidgetIds).toEqual(["ai-insight"]);
    expect(screen.getByRole("checkbox", { name: "AI Insight" })).not.toBeChecked();
  });

  it("re-checking a hidden widget restores it", () => {
    useDashboardPreferencesStore.setState({ hiddenWidgetIds: ["ai-insight"] });
    render(<DashboardCustomizeMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Customize dashboard" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "AI Insight" }));

    expect(useDashboardPreferencesStore.getState().hiddenWidgetIds).toEqual([]);
  });
});
