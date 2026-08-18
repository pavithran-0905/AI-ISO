import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MonitoringEventsPage } from "@/features/monitoring/pages/monitoring-events-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/monitoring/events",
}));

describe("MonitoringEventsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the page header and loads real event data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: "ok",
            data: {
              events: [
                {
                  id: "e1",
                  event_kind: "deployment",
                  severity: "info",
                  title: "Deployed api-gateway-service",
                  occurred_at: "2026-01-01T00:00:00Z",
                  ended_at: null,
                  service_name: "api-gateway-service",
                },
              ],
              page: { next_cursor: null, has_more: false },
            },
            meta: {},
          }),
      }),
    );

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MonitoringEventsPage />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Events" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Deployed api-gateway-service")).toBeInTheDocument());
  });
});
