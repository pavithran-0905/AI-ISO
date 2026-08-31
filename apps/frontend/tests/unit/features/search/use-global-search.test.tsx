import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useGlobalSearch } from "@/features/search/hooks/use-global-search";
import { usePermissions } from "@/permissions/hooks";
import { useSelectedOrganization } from "@/organization/use-organizations";

vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/organization/use-organizations", () => ({ useSelectedOrganization: vi.fn() }));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mockOrg(selectedOrganizationId: string | null) {
  vi.mocked(useSelectedOrganization).mockReturnValue({
    organizations: undefined,
    isLoading: false,
    isError: false,
    error: null,
    selectedOrganizationId,
    needsSelection: false,
    hasNoAccess: false,
  });
}

function mockRole(isAdministrative: boolean) {
  vi.mocked(usePermissions).mockReturnValue({ role: isAdministrative ? "super_admin" : "operator", can: vi.fn(), isReadOnly: false, isAdministrative } as unknown as ReturnType<
    typeof usePermissions
  >);
}

function mockBackend() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });
      if (url.includes("/inventory/search")) {
        return respond({ items: [{ id: "a1", organization_id: "org-1", project_id: null, name: "edge-01", display_name: "edge-01", hostname: "edge-01.internal", asset_type: "physical_server", status: "managed", health: "healthy" }], pagination: { total: 1, page: 1, page_size: 5, total_pages: 1, has_next: false, has_previous: false } });
      }
      if (url.includes("/users/search")) {
        return respond([{ id: "u1", username: "sarun", email: "sarun@example.com", display_name: "Sarun M", avatar: null, status: "active", created_at: "2026-01-01T00:00:00Z" }]);
      }
      if (url.includes("/alerts?")) {
        return respond([{ id: "al1", organization_id: "org-1", project_id: null, rule_id: null, source: "monitoring", severity: "high", status: "open", title: "CPU threshold exceeded", message: "CPU above 90%", fingerprint: "f1", source_reference: {}, assigned_to: null, triggered_at: "2026-01-01T00:00:00Z", resolved_at: null, closed_at: null }]);
      }
      if (url.includes("/automation/jobs?") || url.includes("/automation/jobs")) {
        return respond([]);
      }
      if (url.includes("/reports?")) return respond([]);
      if (url.includes("/ai/conversations")) return respond([]);
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

describe("useGlobalSearch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns no groups below the minimum query length, without fetching anything", async () => {
    mockOrg("org-1");
    mockRole(false);
    mockBackend();
    const { result } = renderHook(() => useGlobalSearch("e", true), { wrapper });
    expect(result.current.groups).toEqual([]);
    expect(result.current.queryLongEnough).toBe(false);
  });

  it("searches real assets and alerts, and omits Users for a non-administrative session", async () => {
    mockOrg("org-1");
    mockRole(false);
    mockBackend();
    const { result } = renderHook(() => useGlobalSearch("edge", true), { wrapper });

    await waitFor(() => expect(result.current.groups.find((g) => g.type === "asset")?.results).toHaveLength(1));
    expect(result.current.groups.find((g) => g.type === "user")).toBeUndefined();
  });

  it("includes real Users results for an administrative session", async () => {
    mockOrg("org-1");
    mockRole(true);
    mockBackend();
    const { result } = renderHook(() => useGlobalSearch("sarun", true), { wrapper });

    await waitFor(() => expect(result.current.groups.find((g) => g.type === "user")?.results).toHaveLength(1));
  });

  it("filters alerts client-side by title, since that route has no free-text search parameter", async () => {
    mockOrg("org-1");
    mockRole(false);
    mockBackend();
    const { result } = renderHook(() => useGlobalSearch("cpu", true), { wrapper });

    await waitFor(() => expect(result.current.groups.find((g) => g.type === "alert")?.results).toHaveLength(1));
    expect(result.current.groups.find((g) => g.type === "alert")?.results[0].title).toBe("CPU threshold exceeded");
  });

  it("does not fetch anything when inactive (palette closed)", () => {
    mockOrg("org-1");
    mockRole(false);
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    renderHook(() => useGlobalSearch("edge", false), { wrapper });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
