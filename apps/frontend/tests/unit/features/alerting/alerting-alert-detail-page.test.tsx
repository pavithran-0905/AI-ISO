import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertingAlertDetailPage } from "@/features/alerting/pages/alerting-alert-detail-page";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
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

      if (url.includes("/alerts/a1/history")) return respond([]);
      if (url.includes("/alerts/a1/acknowledgements")) return respond([]);
      if (url.includes("/alerts/a1/correlations")) return respond([]);
      if (url.includes("/alerts/a1/notifications")) return respond([]);
      if (url.includes("/alerts/a1")) {
        return respond({
          id: "a1",
          organization_id: "org-1",
          project_id: null,
          rule_id: null,
          source: "monitoring",
          severity: "critical",
          status: "open",
          title: "Database unreachable",
          message: "Connection refused",
          fingerprint: "fp-1",
          source_reference: { host: "db-01" },
          assigned_to: null,
          triggered_at: "2026-01-01T00:00:00Z",
          resolved_at: null,
          closed_at: null,
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
      <AlertingAlertDetailPage alertId="a1" />
    </QueryClientProvider>,
  );
}

describe("AlertingAlertDetailPage", () => {
  afterEach(() => {
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("loads the real alert and renders its identity and description", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Database unreachable" })).toBeInTheDocument());
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
    expect(screen.getByText("db-01")).toBeInTheDocument();
  });

  it("navigates back to the Alerts list", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Back to Alerts" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Back to Alerts" }));

    expect(push).toHaveBeenCalledWith("/alerting/alerts");
  });
});
