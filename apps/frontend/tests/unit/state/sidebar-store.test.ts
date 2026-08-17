import { afterEach, describe, expect, it } from "vitest";

import { useSidebarStore } from "@/state/sidebar-store";

describe("useSidebarStore", () => {
  afterEach(() => {
    useSidebarStore.setState({ collapsed: false, collapsedGroups: {} });
  });

  it("starts expanded with no groups collapsed", () => {
    expect(useSidebarStore.getState().collapsed).toBe(false);
    expect(useSidebarStore.getState().collapsedGroups).toEqual({});
  });

  it("toggle() flips collapsed", () => {
    useSidebarStore.getState().toggle();
    expect(useSidebarStore.getState().collapsed).toBe(true);

    useSidebarStore.getState().toggle();
    expect(useSidebarStore.getState().collapsed).toBe(false);
  });

  it("setCollapsed() sets collapsed explicitly", () => {
    useSidebarStore.getState().setCollapsed(true);
    expect(useSidebarStore.getState().collapsed).toBe(true);

    useSidebarStore.getState().setCollapsed(true);
    expect(useSidebarStore.getState().collapsed).toBe(true);
  });

  it("toggleGroup() flips a single group's entry without touching others", () => {
    useSidebarStore.getState().toggleGroup("operations");
    expect(useSidebarStore.getState().collapsedGroups).toEqual({ operations: true });

    useSidebarStore.getState().toggleGroup("platform");
    expect(useSidebarStore.getState().collapsedGroups).toEqual({ operations: true, platform: true });

    useSidebarStore.getState().toggleGroup("operations");
    expect(useSidebarStore.getState().collapsedGroups).toEqual({ operations: false, platform: true });
  });
});
