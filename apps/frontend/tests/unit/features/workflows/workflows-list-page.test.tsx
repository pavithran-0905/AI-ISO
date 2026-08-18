import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkflowsListPage } from "@/features/workflows/pages/workflows-list-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/workflows",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function workflowBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "w1",
    organization_id: "org-1",
    project_id: null,
    workflow_key: "onboard-server",
    name: "Onboard server",
    description: null,
    owner: "platform-team",
    tags: ["provisioning"],
    default_variables: {},
    current_version_number: "1",
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
      if (url.includes("/workflows?")) {
        return respond([workflowBody(), workflowBody({ id: "w2", name: "Decommission server", workflow_key: "decommission-server" })]);
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkflowsListPage />
    </QueryClientProvider>,
  );
}

describe("WorkflowsListPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real workflow", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByText("Onboard server")).toBeInTheDocument());
    expect(screen.getByText("Decommission server")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Onboard server/ })).toHaveAttribute("href", "/workflows/w1");
  });

  it("filters client-side by the free-text search term", async () => {
    mockSearch.current = "q=onboard";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByText("Onboard server")).toBeInTheDocument());
    expect(screen.queryByText("Decommission server")).not.toBeInTheDocument();
  });

  it("pushes a URL with the search query so the filtered view is shareable", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Search")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "onboard" } });

    expect(push).toHaveBeenCalledWith("/workflows?q=onboard");
  });
});
