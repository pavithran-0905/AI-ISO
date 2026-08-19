import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useSettingsNavItems } from "@/features/settings/lib/nav-items";
import { usePermissions } from "@/permissions/hooks";

vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));

describe("useSettingsNavItems", () => {
  it("omits System for a non-administrative role", () => {
    vi.mocked(usePermissions).mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);
    const { result } = renderHook(() => useSettingsNavItems());
    expect(result.current.map((item) => item.href)).not.toContain("/settings/system");
  });

  it("includes System for an administrative role", () => {
    vi.mocked(usePermissions).mockReturnValue({ role: "organization_admin", can: () => true, isReadOnly: false, isAdministrative: true } as unknown as ReturnType<typeof usePermissions>);
    const { result } = renderHook(() => useSettingsNavItems());
    expect(result.current.map((item) => item.href)).toContain("/settings/system");
  });
});
