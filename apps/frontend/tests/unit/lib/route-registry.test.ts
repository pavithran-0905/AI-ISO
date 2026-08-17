import { describe, expect, it } from "vitest";

import { getNavRoutes, getRouteMeta, ROUTE_REGISTRY } from "@/lib/route-registry";

describe("route-registry", () => {
  it("registers the dashboard route", () => {
    expect(getRouteMeta("/")).toMatchObject({ title: "Dashboard", showInNav: true });
  });

  it("returns undefined for an unregistered path", () => {
    expect(getRouteMeta("/does-not-exist")).toBeUndefined();
  });

  it("getNavRoutes only returns routes marked showInNav", () => {
    const navRoutes = getNavRoutes();
    expect(navRoutes.every((route) => route.showInNav)).toBe(true);
    expect(navRoutes.length).toBeGreaterThan(0);
  });

  it("every registered route has a non-empty title and breadcrumb", () => {
    for (const route of ROUTE_REGISTRY) {
      expect(route.title.length).toBeGreaterThan(0);
      expect(route.breadcrumb.length).toBeGreaterThan(0);
    }
  });
});
