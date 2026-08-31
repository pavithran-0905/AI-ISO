import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditActivityPage } from "@/features/audit/pages/audit-activity-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/audit/activity",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function auditEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: "evt-1",
    action: "finding_raised",
    entity_type: "finding",
    entity_id: "f-1",
    entity_reference: "Unencrypted volume detected",
    actor_id: "user-1",
    actor_type: "user",
    occurred_at: "2026-08-01T10:00:00Z",
    summary: "A finding was raised.",
    succeeded: true,
    changes: {},
    ...overrides,
  };
}

function mockBackend(overrides: { complianceEvents?: unknown[]; complianceStatus?: number } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/compliance/audit?")) {
        if (overrides.complianceStatus === 500) {
          return Promise.resolve({
            status: 500,
            ok: false,
            json: () => Promise.resolve({ success: false, message: "Internal error.", error: { code: "AIIOS-INTERNAL", details: [] }, meta: {} }),
          });
        }
        return respond(overrides.complianceEvents ?? [auditEntry()]);
      }
      if (url.includes("/integrations/audit?")) return respond([auditEntry({ id: "evt-2", action: "connector_enabled", entity_type: "connector", entity_reference: "Slack" })]);
      if (url.includes("/notifications/audit?")) return respond([auditEntry({ id: "evt-3", action: "broadcast_initiated", entity_type: "broadcast", entity_reference: "Maintenance notice" })]);
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuditActivityPage />
    </QueryClientProvider>,
  );
}

describe("AuditActivityPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
    // A safety net, not the primary reset: if a test times out before
    // reaching its own `vi.useRealTimers()`, fake timers would
    // otherwise leak into every later test in this file and hang them
    // all the same way.
    vi.useRealTimers();
  });

  it("defaults to the compliance source and renders its real events", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0));
    expect(screen.getByRole("tab", { name: "Compliance", selected: true })).toBeInTheDocument();
  });

  it("switches source via the tabs and resets filters/offset in the URL", async () => {
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("tab", { name: "Integrations" }));
    expect(push).toHaveBeenCalledWith("/audit/activity?source=integrations");
  });

  it("renders integrations' events with a warning that the route requires no authentication at all", async () => {
    mockSearch.current = "source=integrations";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Slack").length).toBeGreaterThan(0));
    expect(screen.getByText(/requires no authentication at all/)).toBeInTheDocument();
  });

  it("shows only compliance's real filters, and pushes a debounced actor-id filter into the URL", async () => {
    mockBackend();
    renderPage();
    // The initial data load goes through real fetch/TanStack Query
    // timers, so it must resolve under real timers — only the
    // debounce itself runs under fake ones.
    await waitFor(() => expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0));

    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText("Actor ID"), { target: { value: "user-9" } });
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(push).toHaveBeenCalledWith("/audit/activity?actorId=user-9");
    vi.useRealTimers();
  });

  it("pages forward using the real offset/limit, never a fabricated total", async () => {
    mockBackend({ complianceEvents: Array.from({ length: 25 }, (_, i) => auditEntry({ id: `evt-${i}` })) });
    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(push).toHaveBeenCalledWith("/audit/activity?offset=25");
  });

  it("shows an empty state when the real result set is empty", async () => {
    mockBackend({ complianceEvents: [] });
    renderPage();
    await waitFor(() => expect(screen.getByText("No events found")).toBeInTheDocument());
  });

  it("shows a retry-capable error state on a backend failure, not a blank page", async () => {
    mockBackend({ complianceStatus: 500 });
    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument());
  });

  it("switches between Table and Timeline over the same already-fetched data, without a new fetch", async () => {
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0));
    const fetchCallsBeforeToggle = vi.mocked(fetch).mock.calls.length;

    fireEvent.click(screen.getByRole("radio", { name: "Timeline" }));
    expect(screen.getByRole("list").tagName).toBe("OL");
    expect(vi.mocked(fetch).mock.calls.length).toBe(fetchCallsBeforeToggle);
  });

  it("opens the event detail drawer from a table row and shows the real event's fields", async () => {
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("button", { name: "View" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("user-1")).toBeInTheDocument();
  });

  it("shows the export control only for the compliance source", async () => {
    mockBackend();
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0));
    expect(screen.getByLabelText("Export format")).toBeInTheDocument();
  });

  it("shows no export control for notifications, since that service has no report-generation route at all", async () => {
    mockSearch.current = "source=notifications";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Maintenance notice").length).toBeGreaterThan(0));
    expect(screen.queryByLabelText("Export format")).not.toBeInTheDocument();
  });
});
