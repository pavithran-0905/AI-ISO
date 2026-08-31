import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useSession } from "@/auth/session";
import { NotificationCenterPage } from "@/features/notifications/pages/notification-center-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/notifications",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));
vi.mock("@/auth/session", () => ({ useSession: vi.fn() }));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function notificationBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "n1",
    organization_id: "org-1",
    user_id: "user-1",
    category: "alert",
    priority: "critical",
    status: "sent",
    subject: "Disk usage above threshold",
    body: "Disk usage on edge-01 exceeded 90%.",
    template_id: null,
    source_service: "monitoring-service",
    source_event_type: null,
    correlation_id: null,
    expires_at: null,
    read_at: null,
    acknowledged_at: null,
    tags: [],
    notification_metadata: {},
    created_at: "2026-08-01T10:00:00Z",
    updated_at: "2026-08-01T10:00:00Z",
    ...overrides,
  };
}

function mockBackend(items: unknown[] = [notificationBody()]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });
      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/notifications?")) return respond(items);
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <NotificationCenterPage />
    </QueryClientProvider>,
  );
}

describe("NotificationCenterPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("renders the real notification list and the no-authentication warning", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Disk usage above threshold").length).toBeGreaterThan(0));
    expect(screen.getByText(/checks no identity for reading or changing notifications/)).toBeInTheDocument();
  });

  it("switching to the Unread tab pushes a view=unread URL, without fetching again", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
    mockBackend([notificationBody({ id: "n1", read_at: null }), notificationBody({ id: "n2", subject: "Already read", read_at: "2026-08-01T11:00:00Z" })]);
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Disk usage above threshold").length).toBeGreaterThan(0));
    const fetchCallsBeforeToggle = vi.mocked(fetch).mock.calls.length;

    fireEvent.click(screen.getByRole("tab", { name: "Unread" }));
    expect(push).toHaveBeenCalledWith("/notifications?view=unread");
    expect(vi.mocked(fetch).mock.calls.length).toBe(fetchCallsBeforeToggle);
  });

  it("filters to Unread client-side over the loaded page, on a real navigation", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
    mockSearch.current = "view=unread";
    mockBackend([notificationBody({ id: "n1", read_at: null }), notificationBody({ id: "n2", subject: "Already read", read_at: "2026-08-01T11:00:00Z" })]);
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Disk usage above threshold").length).toBeGreaterThan(0));
    expect(screen.queryAllByText("Already read")).toHaveLength(0);
  });

  it("shows an empty state when the real result set is empty", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
    mockBackend([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("You're all caught up")).toBeInTheDocument());
  });

  it("pushes a URL with the real category filter", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Disk usage above threshold").length).toBeGreaterThan(0));

    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "alert" } });
    expect(push).toHaveBeenCalledWith("/notifications?category=alert");
  });

  it("links to Settings for preferences rather than duplicating them here", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Disk usage above threshold").length).toBeGreaterThan(0));
    expect(screen.getByRole("link", { name: "Preferences" })).toHaveAttribute("href", "/settings/notifications");
  });
});
