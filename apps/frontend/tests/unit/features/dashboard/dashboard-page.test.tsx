import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { useDashboardPreferencesStore } from "@/state/dashboard-preferences-store";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));

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

const INVENTORY_STATISTICS = {
  total_assets: 10,
  total_relationships: 4,
  type_distribution: { physical_server: 6, virtual_machine: 4 },
  health_distribution: { healthy: 7, warning: 2, critical: 1 },
  lifecycle_distribution: {},
  os_distribution: {},
  vendor_distribution: {},
  location_distribution: {},
  computed_at: "2026-01-01T00:00:00Z",
};

const REPORTING_STATISTICS = {
  total_reports: 2,
  total_executions: 5,
  successful_executions: 4,
  failed_executions: 1,
  scheduled_executions: 1,
  total_downloads: 0,
  total_distributions: 0,
  failed_distributions: 0,
  average_duration_ms: 1000,
  popular_reports: {},
  export_format_usage: {},
  template_usage: {},
  schedule_usage: {},
  distribution_usage: {},
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
      if (url.includes("/inventory/statistics")) return respond(INVENTORY_STATISTICS);
      if (url.includes("/reports/statistics")) return respond(REPORTING_STATISTICS);
      if (url.includes("/ai/recommendations")) return respond([]);
      if (url.includes("/compliance/audit")) return respond([]);
      if (url.includes("/notifications")) return respond([]);
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
    // Unmount before resetting shared stores — see the identical note
    // in tests/unit/organization/use-organizations.test.tsx.
    cleanup();
    useOrganizationStore.setState({ selectedOrganizationId: null });
    useDashboardPreferencesStore.setState({ preferredMode: "executive", hiddenWidgetIds: [] });
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real section", async () => {
    mockBackend([ORG_1]);
    renderDashboard();

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("AI Infrastructure OS")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument());
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Asset health")).toBeInTheDocument();
    expect(screen.getByText("Operational health")).toBeInTheDocument();
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText("Recent automation activity")).toBeInTheDocument();
    expect(screen.getByText("System status")).toBeInTheDocument();
    expect(screen.getByText("Quick access")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("gateway")).toBeInTheDocument());

    // The optional widget grid (§26) — Executive mode by default.
    await waitFor(() => expect(screen.getByRole("heading", { name: "Reporting" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "AI Insight" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Operations Workspace" })).not.toBeInTheDocument();

    // Real asset-health counts (§10/§11) — from the seeded distribution.
    await waitFor(() => expect(screen.getByText("Healthy")).toBeInTheDocument());
    expect(screen.getByText("Critical")).toBeInTheDocument();
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

  it("switching to Operations mode swaps which optional widgets render, and pushes the URL", async () => {
    mockBackend([ORG_1]);
    renderDashboard();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Reporting" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("radio", { name: "Operations" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("mode=operations"));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Operations Workspace" })).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Reporting" })).not.toBeInTheDocument();
  });

  it("respects an explicit ?mode= URL param over the stored preference", async () => {
    useDashboardPreferencesStore.setState({ preferredMode: "executive", hiddenWidgetIds: [] });
    mockSearch.current = "mode=operations";
    mockBackend([ORG_1]);
    renderDashboard();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Operations Workspace" })).toBeInTheDocument());
  });

  it("Customize menu hides an optional widget, persisted to the preferences store", async () => {
    mockBackend([ORG_1]);
    renderDashboard();

    await waitFor(() => expect(screen.getByRole("heading", { name: "AI Insight" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Customize dashboard" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "AI Insight" }));

    expect(screen.queryByRole("heading", { name: "AI Insight" })).not.toBeInTheDocument();
    expect(useDashboardPreferencesStore.getState().hiddenWidgetIds).toContain("ai-insight");
  });

  it("Quick Access links to real, registered routes", async () => {
    mockBackend([ORG_1]);
    renderDashboard();

    await waitFor(() => expect(screen.getByText("Quick access")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Infrastructure" })).toHaveAttribute("href", "/infrastructure");
  });
});
