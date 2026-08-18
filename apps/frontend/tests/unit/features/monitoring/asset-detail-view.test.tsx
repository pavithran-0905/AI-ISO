import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssetDetailView } from "@/features/monitoring/components/asset-detail-view";
import { useAssetRelationships } from "@/features/monitoring/hooks/use-asset-relationships";
import type { Asset } from "@/features/monitoring/types";

vi.mock("@/features/monitoring/hooks/use-asset-relationships", () => ({
  useAssetRelationships: vi.fn(),
}));

const mockedRelationships = vi.mocked(useAssetRelationships);

const ASSET: Asset = {
  id: "a1",
  organizationId: "org-1",
  projectId: null,
  name: "db-01",
  displayName: "Primary DB",
  hostname: "db-01.internal",
  fqdn: "db-01.internal.example.com",
  ipAddress: "10.0.0.5",
  vendor: "Acme",
  manufacturer: null,
  model: null,
  operatingSystem: "Linux",
  environment: "production",
  assetType: "database",
  categoryId: "cat-1",
  classId: null,
  locationId: null,
  ownerId: null,
  status: "managed",
  health: "warning",
  lifecycleState: "operational",
  criticality: "high",
  metadata: { rack: "12A" },
  tags: ["critical-path"],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-02T00:00:00Z",
};

describe("AssetDetailView", () => {
  it("renders identity, health, and metadata from real asset fields", () => {
    mockedRelationships.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAssetRelationships>);

    render(<AssetDetailView asset={ASSET} />);

    expect(screen.getByText("db-01.internal")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.5")).toBeInTheDocument();
    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByText("managed")).toBeInTheDocument();
    expect(screen.getByText("critical-path")).toBeInTheDocument();
    // category_id has no name-resolution endpoint — shown as a raw id, labeled honestly.
    expect(screen.getByText("Category id")).toBeInTheDocument();
    expect(screen.getByText("cat-1")).toBeInTheDocument();
  });

  it("links related assets by id when relationships exist", () => {
    mockedRelationships.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [{ id: "r1", sourceAssetId: "a1", targetAssetId: "a2", relationshipType: "depends_on", customLabel: null }],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAssetRelationships>);

    render(<AssetDetailView asset={ASSET} />);

    expect(screen.getByText("depends_on")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "a2" })).toHaveAttribute("href", "/monitoring/assets/a2");
  });

  it("shows an honest empty state when no relationships are recorded", () => {
    mockedRelationships.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAssetRelationships>);

    render(<AssetDetailView asset={ASSET} />);

    expect(screen.getByText("No related assets")).toBeInTheDocument();
  });
});
