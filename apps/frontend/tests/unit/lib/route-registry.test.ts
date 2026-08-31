import { describe, expect, it } from "vitest";

import {
  getBreadcrumbTrail,
  getNavGroups,
  getNavRoutes,
  getRouteById,
  getRouteMeta,
  NAV_GROUPS,
  ROUTE_REGISTRY,
} from "@/lib/route-registry";

describe("route-registry", () => {
  it("registers the dashboard route as implemented", () => {
    expect(getRouteMeta("/")).toMatchObject({ title: "Dashboard", showInNav: true, visibility: "implemented" });
  });

  it("returns undefined for an unregistered path", () => {
    expect(getRouteMeta("/does-not-exist")).toBeUndefined();
  });

  it("getRouteById finds a route by its stable id", () => {
    expect(getRouteById("dashboard")).toMatchObject({ path: "/" });
    expect(getRouteById("does-not-exist")).toBeUndefined();
  });

  it("getNavRoutes only returns routes marked showInNav with a nav group", () => {
    const navRoutes = getNavRoutes();
    expect(navRoutes.every((route) => route.showInNav && route.navGroup !== null)).toBe(true);
    expect(navRoutes.length).toBeGreaterThan(0);
  });

  it("the design-system route is excluded from nav (showInNav: false)", () => {
    const navRoutes = getNavRoutes();
    expect(navRoutes.some((route) => route.id === "design-system")).toBe(false);
  });

  it("every registered route has a non-empty title and breadcrumb", () => {
    for (const route of ROUTE_REGISTRY) {
      expect(route.title.length).toBeGreaterThan(0);
      expect(route.breadcrumb.length).toBeGreaterThan(0);
    }
  });

  it("every planned route has no real page — never claim implemented without one", () => {
    const plannedRoutes = ROUTE_REGISTRY.filter((route) => route.visibility === "planned");
    expect(plannedRoutes.length).toBeGreaterThan(0);
    for (const route of plannedRoutes) {
      expect(route.feature).not.toBeNull();
    }
  });

  it("Prompt 014 promotes the 'users' stub to implemented, restricted to administrators, with a real sub-family", () => {
    expect(getRouteMeta("/administration/users")).toMatchObject({
      id: "users",
      visibility: "implemented",
      showInNav: true,
      roles: ["super_admin", "organization_admin"],
    });
    for (const id of ["administration-teams", "administration-roles", "administration-permissions", "administration-invitations"]) {
      expect(getRouteById(id)).toMatchObject({ visibility: "implemented", showInNav: false, roles: ["super_admin", "organization_admin"] });
    }
  });

  it("Prompt 015 registers Audit & Activity as two real routes, restricted to administrators, distinct from the still-planned Compliance stub", () => {
    expect(getRouteMeta("/audit")).toMatchObject({
      id: "audit",
      visibility: "implemented",
      showInNav: true,
      roles: ["super_admin", "organization_admin"],
    });
    expect(getRouteById("audit-activity")).toMatchObject({
      path: "/audit/activity",
      visibility: "implemented",
      showInNav: false,
      roles: ["super_admin", "organization_admin"],
    });
    expect(getRouteById("compliance")).toMatchObject({ visibility: "planned" });
  });

  it("every route id is unique", () => {
    const ids = ROUTE_REGISTRY.map((route) => route.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every route path is unique", () => {
    const paths = ROUTE_REGISTRY.map((route) => route.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  describe("getNavGroups", () => {
    const groups = getNavGroups();

    it("returns groups in NAV_GROUPS order, skipping empty ones", () => {
      const order = groups.map((entry) => entry.group);
      const expectedOrder = NAV_GROUPS.filter((group) => order.includes(group));
      expect(order).toEqual(expectedOrder);
    });

    it("every group has at least one route and a label/icon", () => {
      for (const entry of groups) {
        expect(entry.routes.length).toBeGreaterThan(0);
        expect(entry.label.length).toBeGreaterThan(0);
        expect(entry.icon).toBeDefined();
      }
    });

    it("includes every canonical group named in docs/frontend Prompt 003 §3", () => {
      const groupNames = groups.map((entry) => entry.group);
      for (const expected of [
        "overview",
        "operations",
        "automation",
        "intelligence",
        "governance",
        "administration",
        "platform",
      ] as const) {
        expect(groupNames).toContain(expected);
      }
    });
  });

  describe("getBreadcrumbTrail", () => {
    it("returns the route for a registered path", () => {
      expect(getBreadcrumbTrail("/")).toEqual([getRouteMeta("/")]);
    });

    it("returns an empty trail for an unregistered path", () => {
      expect(getBreadcrumbTrail("/does-not-exist")).toEqual([]);
    });
  });
});
