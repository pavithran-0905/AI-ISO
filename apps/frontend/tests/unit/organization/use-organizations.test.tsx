import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useOrganizationStore } from "@/organization/store";
import { useSelectedOrganization } from "@/organization/use-organizations";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mockOrganizations(organizations: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: () => Promise.resolve({ success: true, message: "ok", data: organizations, meta: {} }),
    }),
  );
}

const ORG_A = { id: "org-a", name: "org-a", display_name: "Org A", short_name: null, slug: "org-a", status: "active" };
const ORG_B = { id: "org-b", name: "org-b", display_name: "Org B", short_name: null, slug: "org-b", status: "active" };

describe("useSelectedOrganization", () => {
  afterEach(() => {
    // Unmount the previous test's hook *before* touching the shared
    // store — otherwise its still-mounted `useEffect` (auto-select) can
    // react to the reset asynchronously (TanStack Query's own update
    // scheduling defers past a plain `act()` flush) and re-set the
    // store during the *next* test.
    cleanup();
    useOrganizationStore.setState({ selectedOrganizationId: null });
    vi.unstubAllGlobals();
  });

  it("auto-selects when the user has exactly one organization", async () => {
    mockOrganizations([ORG_A]);

    const { result } = renderHook(() => useSelectedOrganization(), { wrapper });

    await waitFor(() => expect(result.current.selectedOrganizationId).toBe("org-a"));
    expect(result.current.needsSelection).toBe(false);
    expect(result.current.hasNoAccess).toBe(false);
    expect(useOrganizationStore.getState().selectedOrganizationId).toBe("org-a");
  });

  it("requires explicit selection when the user has more than one organization and none is stored", async () => {
    mockOrganizations([ORG_A, ORG_B]);

    const { result } = renderHook(() => useSelectedOrganization(), { wrapper });

    await waitFor(() => expect(result.current.organizations).toHaveLength(2));
    expect(result.current.needsSelection).toBe(true);
    expect(result.current.selectedOrganizationId).toBeNull();
  });

  it("uses the stored selection when it's still valid, without re-prompting", async () => {
    useOrganizationStore.setState({ selectedOrganizationId: "org-b" });
    mockOrganizations([ORG_A, ORG_B]);

    const { result } = renderHook(() => useSelectedOrganization(), { wrapper });

    await waitFor(() => expect(result.current.selectedOrganizationId).toBe("org-b"));
    expect(result.current.needsSelection).toBe(false);
  });

  it("ignores a stored selection that's no longer in the user's organization list", async () => {
    useOrganizationStore.setState({ selectedOrganizationId: "org-stale" });
    mockOrganizations([ORG_A, ORG_B]);

    const { result } = renderHook(() => useSelectedOrganization(), { wrapper });

    await waitFor(() => expect(result.current.organizations).toHaveLength(2));
    expect(result.current.selectedOrganizationId).toBeNull();
    expect(result.current.needsSelection).toBe(true);
  });

  it("reports hasNoAccess when the user belongs to zero organizations", async () => {
    mockOrganizations([]);

    const { result } = renderHook(() => useSelectedOrganization(), { wrapper });

    await waitFor(() => expect(result.current.hasNoAccess).toBe(true));
    expect(result.current.needsSelection).toBe(false);
    expect(result.current.selectedOrganizationId).toBeNull();
  });
});
