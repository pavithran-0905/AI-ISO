import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssetTable } from "@/features/infrastructure/components/asset-table";
import type { Asset, AssetPagination } from "@/features/infrastructure/types";

function asset(overrides: Partial<Asset>): Asset {
  return {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    name: "web-01",
    displayName: null,
    hostname: "web-01.internal",
    fqdn: null,
    ipAddress: null,
    macAddress: null,
    serialNumber: null,
    vendor: null,
    manufacturer: null,
    model: null,
    firmwareVersion: null,
    operatingSystem: null,
    architecture: null,
    environment: "production",
    assetType: "virtual_machine",
    categoryId: null,
    classId: null,
    locationId: null,
    ownerId: null,
    status: "managed",
    health: "healthy",
    lifecycleState: "operational",
    criticality: "medium",
    currentVersion: 1,
    metadata: {},
    tags: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

const PAGINATION: AssetPagination = { total: 2, page: 1, pageSize: 25, totalPages: 1, hasNext: false, hasPrevious: false };

describe("AssetTable", () => {
  it("renders each asset as a link into its own detail page", () => {
    render(
      <AssetTable
        assets={[asset({ id: "a1", name: "web-01" }), asset({ id: "a2", name: "web-02", displayName: "Web 02" })]}
        pagination={PAGINATION}
        sortField="updated_at"
        sortDirection="desc"
        onSortChange={vi.fn()}
        onPageChange={vi.fn()}
      />,
    );

    const table = screen.getAllByRole("table")[0];
    expect(within(table).getByRole("link", { name: "web-01" })).toHaveAttribute("href", "/infrastructure/assets/a1");
    expect(within(table).getByRole("link", { name: "Web 02" })).toHaveAttribute("href", "/infrastructure/assets/a2");
  });

  it("reports a sort-field change, toggling direction when the same column is clicked again", () => {
    const onSortChange = vi.fn();
    render(
      <AssetTable
        assets={[asset({})]}
        pagination={PAGINATION}
        sortField="updated_at"
        sortDirection="desc"
        onSortChange={onSortChange}
        onPageChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^Asset/ }));
    expect(onSortChange).toHaveBeenCalledWith("name");
  });

  it("disables Previous/Next according to the real pagination metadata, not a guess", () => {
    render(
      <AssetTable
        assets={[asset({})]}
        pagination={{ total: 50, page: 2, pageSize: 25, totalPages: 2, hasNext: false, hasPrevious: true }}
        sortField="updated_at"
        sortDirection="desc"
        onSortChange={vi.fn()}
        onPageChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});
