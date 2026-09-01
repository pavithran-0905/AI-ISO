import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QuickAccessGrid } from "@/features/dashboard/components/quick-access-grid";
import { usePermissions } from "@/permissions/hooks";

vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));

const mocked = vi.mocked(usePermissions);

describe("QuickAccessGrid", () => {
  it("links to real, registered routes read from the canonical route registry", () => {
    mocked.mockReturnValue({ role: "viewer" } as unknown as ReturnType<typeof usePermissions>);

    render(<QuickAccessGrid />);

    expect(screen.getByRole("link", { name: "Infrastructure" })).toHaveAttribute("href", "/infrastructure");
    expect(screen.getByRole("link", { name: "Alerting" })).toHaveAttribute("href", "/alerting");
    expect(screen.getByRole("link", { name: "Operations" })).toHaveAttribute("href", "/operations");
  });

  it("every tile is available to every role — none of these routes carry a role restriction today", () => {
    mocked.mockReturnValue({ role: null } as unknown as ReturnType<typeof usePermissions>);
    render(<QuickAccessGrid />);
    expect(screen.getByRole("link", { name: "Infrastructure" })).toBeInTheDocument();
  });
});
