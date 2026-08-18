import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { useOrganizationStore } from "@/organization/store";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

const ORG_1 = { id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" };
const ORG_2 = { id: "org-2", name: "org-2", display_name: "Org Two", short_name: null, slug: "org-2", status: "active" };

const STATISTICS = {
  organization_id: "org-1",
  user_count: 5,
  project_count: 2,
  asset_count: 10,
  workflow_count: 1,
  automation_count: 3,
  validation_count: 0,
  computed_at: "2026-01-01T00:00:00Z",
};

function mockBackend(organizations: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) =>
        Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/organizations/") && url.includes("/analytics")) return respond(STATISTICS);
      if (url.includes("/organizations")) return respond(organizations);
      if (url.includes("/gateway/health")) return respond({ overall_status: "healthy", instances: [] });
      if (url.includes("/alerts")) return respond([]);
      if (url.includes("/automation/executions")) return respond([]);
      if (url.includes("/health")) return respond({ status: "healthy", service: "gateway", version: "0.1.0", environment: "development" });
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  afterEach(() => {
    // Unmount before resetting the shared store — see the identical
    // note in tests/unit/organization/use-organizations.test.tsx.
    cleanup();
    useOrganizationStore.setState({ selectedOrganizationId: null });
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real section", async () => {
    mockBackend([ORG_1]);
    renderDashboard();

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument());
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Operational health")).toBeInTheDocument();
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText("Recent automation activity")).toBeInTheDocument();
    expect(screen.getByText("System status")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("gateway")).toBeInTheDocument());
  });

  it("shows the organization picker when the user belongs to more than one, and switches on selection", async () => {
    mockBackend([ORG_1, ORG_2]);
    renderDashboard();

    await waitFor(() => expect(screen.getByRole("button", { name: "Org One" })).toBeInTheDocument());
    expect(screen.queryByText("Overview")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Org One" }));

    await waitFor(() => expect(screen.getByText("Overview")).toBeInTheDocument());
  });

  it("shows an honest no-access state when the user has zero organizations", async () => {
    mockBackend([]);
    renderDashboard();

    await waitFor(() => expect(screen.getByText("No organization access yet")).toBeInTheDocument());
  });

  it("has a working refresh action", async () => {
    mockBackend([ORG_1]);
    renderDashboard();

    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument());

    const refreshButton = screen.getByRole("button", { name: "Refresh dashboard" });
    fireEvent.click(refreshButton);

    await waitFor(() => expect(refreshButton).not.toHaveAttribute("aria-busy", "true"));
  });
});
