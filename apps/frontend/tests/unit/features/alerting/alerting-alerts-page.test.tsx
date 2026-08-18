import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertingAlertsPage } from "@/features/alerting/pages/alerting-alerts-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/alerting/alerts",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function alertBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "a1",
    organization_id: "org-1",
    project_id: null,
    rule_id: null,
    source: "monitoring",
    severity: "critical",
    status: "open",
    title: "Database unreachable",
    message: "m",
    fingerprint: "fp-1",
    source_reference: {},
    assigned_to: null,
    triggered_at: "2026-01-01T00:00:00Z",
    resolved_at: null,
    closed_at: null,
    ...overrides,
  };
}

function mockBackend() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) =>
        Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/alerts?")) {
        return respond([
          alertBody(),
          alertBody({ id: "a2", title: "Disk almost full", severity: "low", triggered_at: "2026-01-02T00:00:00Z" }),
        ]);
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AlertingAlertsPage />
    </QueryClientProvider>,
  );
}

describe("AlertingAlertsPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real alert", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Database unreachable" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Disk almost full" })).toBeInTheDocument();
  });

  it("pushes a URL with the search query so the filtered view is shareable", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Search")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "disk" } });

    expect(push).toHaveBeenCalledWith("/alerting/alerts?q=disk");
  });

  it("filters client-side by the free-text search term over the complete result set", async () => {
    mockSearch.current = "q=disk";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Disk almost full" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Database unreachable" })).not.toBeInTheDocument();
  });

  it("reads the initial status filter from the URL", async () => {
    mockSearch.current = "status=open";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Status")).toHaveValue("open"));
  });
});
