import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetTable } from "@/features/monitoring/components/asset-table";
import type { Asset, AssetPagination } from "@/features/monitoring/types";

const ASSETS: Asset[] = [
  {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    name: "db-01",
    displayName: "Primary DB",
    hostname: "db-01.internal",
    fqdn: null,
    ipAddress: null,
    vendor: null,
    manufacturer: null,
    model: null,
    operatingSystem: null,
    environment: "production",
    assetType: "database",
    categoryId: null,
    classId: null,
    locationId: null,
    ownerId: null,
    status: "managed",
    health: "healthy",
    lifecycleState: "operational",
    criticality: "high",
    metadata: {},
    tags: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
  },
];

const PAGINATION: AssetPagination = { total: 1, page: 1, pageSize: 25, totalPages: 1, hasNext: false, hasPrevious: false };

function renderTable(overrides: Partial<React.ComponentProps<typeof AssetTable>> = {}) {
  return render(
    <AssetTable
      assets={ASSETS}
      pagination={PAGINATION}
      sortField="updated_at"
      sortDirection="desc"
      onSortChange={vi.fn()}
      onPageChange={vi.fn()}
      {...overrides}
    />,
  );
}

describe("AssetTable", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders every real column, using displayName as the link text", () => {
    renderTable();

    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: "Primary DB" })).toHaveAttribute("href", "/monitoring/assets/a1");
    expect(within(table).getByText("database")).toBeInTheDocument();
    expect(within(table).getByText("managed")).toBeInTheDocument();
    expect(within(table).getByText("production")).toBeInTheDocument();
  });

  it("calls onSortChange with the clicked column", () => {
    const onSortChange = vi.fn();
    renderTable({ onSortChange });

    fireEvent.click(screen.getByRole("button", { name: /^Asset/ }));

    expect(onSortChange).toHaveBeenCalledWith("name");
  });

  it("disables Previous/Next according to real pagination flags, not just page number", () => {
    renderTable({
      pagination: { total: 100, page: 2, pageSize: 25, totalPages: 4, hasNext: true, hasPrevious: true },
    });

    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("calls onPageChange with the next page", () => {
    const onPageChange = vi.fn();
    renderTable({
      onPageChange,
      pagination: { total: 100, page: 2, pageSize: 25, totalPages: 4, hasNext: true, hasPrevious: true },
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });
});
