import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetDetailView } from "@/features/infrastructure/components/asset-detail-view";
import { useAllAssets, useDeleteAsset } from "@/features/infrastructure/hooks/use-assets";
import { useAssetRelationships, useCreateRelationship, useDeleteRelationship } from "@/features/infrastructure/hooks/use-relationships";
import { useTopology } from "@/features/infrastructure/hooks/use-topology";
import type { Asset } from "@/features/infrastructure/types";
import { usePermissions } from "@/permissions/hooks";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));
vi.mock("@/features/infrastructure/hooks/use-assets", async () => {
  const actual = await vi.importActual<typeof import("@/features/infrastructure/hooks/use-assets")>(
    "@/features/infrastructure/hooks/use-assets",
  );
  return { ...actual, useAllAssets: vi.fn(), useDeleteAsset: vi.fn() };
});
vi.mock("@/features/infrastructure/hooks/use-relationships", () => ({
  useAssetRelationships: vi.fn(),
  useCreateRelationship: vi.fn(),
  useDeleteRelationship: vi.fn(),
}));
vi.mock("@/features/infrastructure/hooks/use-topology", () => ({ useTopology: vi.fn() }));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));

const ASSET: Asset = {
  id: "a1",
  organizationId: "org-1",
  projectId: null,
  name: "db-01",
  displayName: "Primary DB",
  hostname: "db-01.internal",
  fqdn: null,
  ipAddress: "10.0.0.5",
  macAddress: null,
  serialNumber: null,
  vendor: "Dell",
  manufacturer: null,
  model: null,
  firmwareVersion: null,
  operatingSystem: "Ubuntu 24.04",
  architecture: null,
  environment: "production",
  assetType: "database",
  categoryId: null,
  classId: null,
  locationId: null,
  ownerId: null,
  status: "managed",
  health: "critical",
  lifecycleState: "operational",
  criticality: "high",
  currentVersion: 3,
  metadata: { region: "us-east-1", api_key: "sk-should-not-render-raw" },
  tags: ["prod", "tier-1"],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-05T00:00:00Z",
};

function mockHooks() {
  vi.mocked(useAllAssets).mockReturnValue({ data: [] } as unknown as ReturnType<typeof useAllAssets>);
  vi.mocked(useDeleteAsset).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDeleteAsset>);
  vi.mocked(useAssetRelationships).mockReturnValue({ data: [], isLoading: false, isError: false } as unknown as ReturnType<typeof useAssetRelationships>);
  vi.mocked(useCreateRelationship).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useCreateRelationship>);
  vi.mocked(useDeleteRelationship).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDeleteRelationship>);
  vi.mocked(useTopology).mockReturnValue({ data: { rootAssetId: "a1", queryKind: "neighbors", nodes: [] }, isLoading: false, isError: false } as unknown as ReturnType<typeof useTopology>);
  vi.mocked(usePermissions).mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);
}

describe("AssetDetailView", () => {
  afterEach(() => {
    push.mockClear();
    mockSearch.current = "";
  });

  it("renders identity and state on the default Overview tab", () => {
    mockHooks();
    render(<AssetDetailView asset={ASSET} />);

    expect(screen.getByText("db-01.internal")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.5")).toBeInTheDocument();
    expect(screen.getByText("Ubuntu 24.04")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "View in Topology" })).toHaveAttribute("href", "/infrastructure/topology?focus=a1");
  });

  it("moves Configuration (tags, metadata, masked secrets) behind its own tab", () => {
    mockHooks();
    render(<AssetDetailView asset={ASSET} />);

    expect(screen.queryByText("prod")).not.toBeInTheDocument();
    expect(screen.queryByText("us-east-1")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Configuration" }));
    expect(push).toHaveBeenCalledWith("/infrastructure/assets/a1?tab=configuration");
  });

  it("renders the real Configuration tab content, masking a key that looks sensitive, when the URL selects it", () => {
    mockHooks();
    mockSearch.current = "tab=configuration";
    render(<AssetDetailView asset={ASSET} />);

    expect(screen.getByText("prod")).toBeInTheDocument();
    expect(screen.getByText("us-east-1")).toBeInTheDocument();
    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.queryByText(/sk-should-not-render-raw/)).not.toBeInTheDocument();
  });

  it("switches to the Relationships and Topology tabs on request", () => {
    mockHooks();
    mockSearch.current = "tab=topology";
    render(<AssetDetailView asset={ASSET} />);
    expect(screen.getByRole("tab", { name: "Topology", selected: true })).toBeInTheDocument();
  });
});
