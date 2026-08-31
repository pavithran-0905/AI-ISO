import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditOverviewPage } from "@/features/audit/pages/audit-overview-page";
import { useOrganizationStore } from "@/organization/store";

vi.mock("next/navigation", () => ({
  usePathname: () => "/audit",
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function errorEnvelope(status: number, code: string, message: string) {
  return { status, ok: false, json: () => Promise.resolve({ success: false, message, error: { code, details: [] }, meta: {} }) };
}

function mockBackend(overrides: { auditSummaryStatus?: number } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/compliance/audit/summary")) {
        if (overrides.auditSummaryStatus === 403) return Promise.resolve(errorEnvelope(403, "AIIOS-FORBIDDEN", "Forbidden."));
        return respond({ since: "2026-07-01T00:00:00Z", total: 42, by_action: { finding_raised: 10, control_updated: 5 } });
      }
      if (url.includes("/compliance/findings/summary")) {
        return respond({ open_total: 7, by_severity: { critical: 2, high: 5 }, critical_open: 2, overdue: 1, open_statuses: ["open"] });
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuditOverviewPage />
    </QueryClientProvider>,
  );
}

describe("AuditOverviewPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    vi.unstubAllGlobals();
  });

  it("renders the real compliance audit summary and findings-posture metrics", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("Finding Raised")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("warns that no platform-wide audit log exists, plainly on the page", async () => {
    mockBackend();
    renderPage();
    expect(screen.getByText(/No platform-wide audit log exists/)).toBeInTheDocument();
  });

  it("shows a permission-safe message rather than a generic error on a 403", async () => {
    mockBackend({ auditSummaryStatus: 403 });
    renderPage();

    await waitFor(() => expect(screen.getByText(/access/i)).toBeInTheDocument());
  });
});
