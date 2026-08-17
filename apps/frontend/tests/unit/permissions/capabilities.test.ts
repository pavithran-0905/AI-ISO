import { describe, expect, it } from "vitest";

import { canPerform, isAdministrativeRole, isReadOnlyRole } from "@/permissions/capabilities";

describe("canPerform", () => {
  it("grants every action to super_admin", () => {
    expect(canPerform("super_admin", "delete")).toBe(true);
    expect(canPerform("super_admin", "admin")).toBe(true);
  });

  it("grants viewer only read", () => {
    expect(canPerform("viewer", "read")).toBe(true);
    expect(canPerform("viewer", "create")).toBe(false);
  });

  it("treats a null role as read-only (the documented common case)", () => {
    expect(canPerform(null, "read")).toBe(true);
    expect(canPerform(null, "update")).toBe(false);
  });

  it("grants operator create/update/execute/export but not delete/admin", () => {
    expect(canPerform("operator", "create")).toBe(true);
    expect(canPerform("operator", "delete")).toBe(false);
    expect(canPerform("operator", "admin")).toBe(false);
  });
});

describe("isReadOnlyRole", () => {
  it("is true for viewer and a null role", () => {
    expect(isReadOnlyRole("viewer")).toBe(true);
    expect(isReadOnlyRole(null)).toBe(true);
  });

  it("is false for operator and above", () => {
    expect(isReadOnlyRole("operator")).toBe(false);
    expect(isReadOnlyRole("super_admin")).toBe(false);
  });
});

describe("isAdministrativeRole", () => {
  it("is true only for super_admin and organization_admin", () => {
    expect(isAdministrativeRole("super_admin")).toBe(true);
    expect(isAdministrativeRole("organization_admin")).toBe(true);
    expect(isAdministrativeRole("project_admin")).toBe(false);
    expect(isAdministrativeRole(null)).toBe(false);
  });
});
