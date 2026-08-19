import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetActions } from "@/features/infrastructure/components/asset-actions";
import { useDeleteAsset } from "@/features/infrastructure/hooks/use-assets";
import type { Asset } from "@/features/infrastructure/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/features/infrastructure/hooks/use-assets", async () => {
  const actual = await vi.importActual<typeof import("@/features/infrastructure/hooks/use-assets")>(
    "@/features/infrastructure/hooks/use-assets",
  );
  return { ...actual, useDeleteAsset: vi.fn() };
});
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

const mockedDelete = vi.mocked(useDeleteAsset);
const mockedPermissions = vi.mocked(usePermissions);

const ASSET: Asset = {
  id: "a1",
  organizationId: "org-1",
  projectId: null,
  name: "web-01",
  displayName: "Web 01",
  hostname: null,
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
  environment: null,
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
  updatedAt: "2026-01-01T00:00:00Z",
};

function renderWithClient(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);
}

describe("AssetActions", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows Edit and Delete for a role the coarse capability model grants update/delete to", () => {
    mockedDelete.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDeleteAsset>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderWithClient(<AssetActions asset={ASSET} />);

    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute("href", "/infrastructure/assets/a1/edit");
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("hides Edit and Delete for a read-only role", () => {
    mockedDelete.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDeleteAsset>);
    mockedPermissions.mockReturnValue({ role: "viewer", can: () => false, isReadOnly: true, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderWithClient(<AssetActions asset={ASSET} />);

    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("requires confirmation before deleting, and waits for the backend's response before navigating away", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined);
    mockedDelete.mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof useDeleteAsset>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderWithClient(<AssetActions asset={ASSET} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(mutateAsync).not.toHaveBeenCalled();

    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalledWith("a1"));
    await vi.waitFor(() => expect(toast.success).toHaveBeenCalledWith("Asset deleted"));
    expect(push).toHaveBeenCalledWith("/infrastructure/assets");
  });
});
