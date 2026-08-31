import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NotificationDetailPage } from "@/features/notifications/pages/notification-detail-page";
import { useOrganizationStore } from "@/organization/store";

vi.mock("next/navigation", () => ({
  usePathname: () => "/notifications/n1",
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockBackend() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });
      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/notifications/n1/deliveries")) {
        return respond([
          { id: "d1", notification_id: "n1", channel: "email", status: "delivered", queued_at: "2026-08-01T10:00:00Z", sent_at: "2026-08-01T10:00:05Z", delivered_at: "2026-08-01T10:00:10Z", failed_at: null, attempts_used: 1, provider_message_id: "msg-1", error: null, latency_ms: 240 },
        ]);
      }
      if (url.includes("/notifications/n1")) {
        return respond({
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
        });
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <NotificationDetailPage notificationId="n1" />
    </QueryClientProvider>,
  );
}

describe("NotificationDetailPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    vi.unstubAllGlobals();
  });

  it("loads the real notification and shows its identity, status, and deliveries", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getAllByRole("heading", { name: "Disk usage above threshold" }).length).toBeGreaterThan(0));
    expect(screen.getByText("Disk usage on edge-01 exceeded 90%.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Email")).toBeInTheDocument());
    expect(screen.getByText("Delivered")).toBeInTheDocument();
  });

  it("links back to the Notification Center", async () => {
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getByRole("link", { name: /Back to Notifications/ })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Back to Notifications/ })).toHaveAttribute("href", "/notifications");
  });
});
