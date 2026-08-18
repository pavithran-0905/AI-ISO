import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AutomationsListPage } from "@/features/automation/pages/automations-list-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/automation/automations",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function jobBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "j1",
    organization_id: "org-1",
    project_id: null,
    name: "Patch web fleet",
    description: null,
    automation_type: "patch_management",
    playbook_type: "shell_script",
    status: "active",
    execution_mode: "manual",
    content: "echo hi",
    target_selector: {},
    variables: {},
    tags: [],
    timeout_seconds: null,
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
      if (url.includes("/automation/jobs?")) {
        return respond([jobBody(), jobBody({ id: "j2", name: "Rotate secrets", automation_type: "security_automation" })]);
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AutomationsListPage />
    </QueryClientProvider>,
  );
}

describe("AutomationsListPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real automation", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Patch web fleet" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Rotate secrets" })).toBeInTheDocument();
  });

  it("pushes a URL with the search query so the filtered view is shareable", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Search")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "patch" } });

    expect(push).toHaveBeenCalledWith("/automation/automations?q=patch");
  });

  it("filters client-side by the free-text search term over the complete result set", async () => {
    mockSearch.current = "q=patch";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Patch web fleet" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Rotate secrets" })).not.toBeInTheDocument();
  });
});
