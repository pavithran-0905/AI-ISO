import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportsListPage } from "@/features/reporting/pages/reports-list-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/reporting/reports",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function reportBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "r1",
    organization_id: "org-1",
    project_id: null,
    template_id: null,
    name: "Weekly infra summary",
    description: null,
    category: "infrastructure",
    report_type: "summary",
    default_format: "pdf",
    parameter_values: {},
    filters: [],
    enabled: true,
    owner_id: null,
    ...overrides,
  };
}

function mockBackend() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/reports/favorites/mine")) return respond([]);
      if (url.includes("/reports?")) {
        return respond([reportBody(), reportBody({ id: "r2", name: "Monthly compliance", category: "compliance", report_type: "compliance" })]);
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ReportsListPage />
    </QueryClientProvider>,
  );
}

describe("ReportsListPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real report", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Weekly infra summary" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Monthly compliance" })).toBeInTheDocument();
  });

  it("pushes a URL with the search query so the filtered view is shareable", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Search")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "weekly" } });

    expect(push).toHaveBeenCalledWith("/reporting/reports?q=weekly");
  });

  it("filters client-side by the free-text search term over the complete result set", async () => {
    mockSearch.current = "q=weekly";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Weekly infra summary" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Monthly compliance" })).not.toBeInTheDocument();
  });
});
