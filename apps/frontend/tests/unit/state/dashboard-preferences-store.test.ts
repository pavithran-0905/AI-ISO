import { afterEach, describe, expect, it } from "vitest";

import { useDashboardPreferencesStore } from "@/state/dashboard-preferences-store";

describe("useDashboardPreferencesStore", () => {
  afterEach(() => {
    useDashboardPreferencesStore.setState({ preferredMode: "executive", hiddenWidgetIds: [] });
  });

  it("defaults to executive mode with no hidden widgets", () => {
    const state = useDashboardPreferencesStore.getState();
    expect(state.preferredMode).toBe("executive");
    expect(state.hiddenWidgetIds).toEqual([]);
  });

  it("setPreferredMode updates the mode", () => {
    useDashboardPreferencesStore.getState().setPreferredMode("operations");
    expect(useDashboardPreferencesStore.getState().preferredMode).toBe("operations");
  });

  it("toggleWidget hides then restores a widget", () => {
    const { toggleWidget } = useDashboardPreferencesStore.getState();

    toggleWidget("ai-insight");
    expect(useDashboardPreferencesStore.getState().hiddenWidgetIds).toEqual(["ai-insight"]);

    toggleWidget("ai-insight");
    expect(useDashboardPreferencesStore.getState().hiddenWidgetIds).toEqual([]);
  });

  it("toggleWidget tracks multiple widgets independently", () => {
    const { toggleWidget } = useDashboardPreferencesStore.getState();
    toggleWidget("ai-insight");
    toggleWidget("reporting-status");
    expect(useDashboardPreferencesStore.getState().hiddenWidgetIds).toEqual(["ai-insight", "reporting-status"]);
  });
});
