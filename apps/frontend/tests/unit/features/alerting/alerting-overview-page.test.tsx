import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertingOverviewPage } from "@/features/alerting/pages/alerting-overview-page";
import { useOrganizationStore } from "@/organization/store";

vi.mock("next/navigation", () => ({
  usePathname: () => "/alerting",
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
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
      if (url.includes("/alert-statistics")) {
        return respond({
          total_alerts: 2,
          open_alert_count: 1,
          noise_ratio: 0,
          suppression_rate: 0,
          average_resolution_seconds: null,
          mtta_seconds: null,
          mttr_seconds: null,
          computed_at: "2026-01-01T00:00:00Z",
        });
      }
      if (url.includes("/alerts?")) {
        return respond([
          {
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
          },
        ]);
      }
      if (url.includes("/maintenance-windows")) return respond([]);
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AlertingOverviewPage />
    </QueryClientProvider>,
  );
}

describe("AlertingOverviewPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders the real summary and maintenance sections", async () => {
    mockBackend();
    renderPage();

    expect(screen.getByRole("heading", { name: "Alerting", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Alerts" })).toHaveAttribute("href", "/alerting/alerts");

    await waitFor(() => expect(screen.getByText("Critical")).toBeInTheDocument());
    expect(screen.getByText("Total alerts")).toBeInTheDocument();
    expect(screen.getByText("No active maintenance windows")).toBeInTheDocument();
  });
});
