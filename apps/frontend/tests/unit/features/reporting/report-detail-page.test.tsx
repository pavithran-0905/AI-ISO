import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportDetailPage } from "@/features/reporting/pages/report-detail-page";

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
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/reports/favorites/mine")) return respond([]);
      if (url.includes("/reports/schedules")) return respond([]);
      if (url.includes("/reports/r1/recipients")) return respond([]);
      if (url.includes("/reports/history")) return respond([]);
      if (url.includes("/reports/r1")) {
        return respond({
          id: "r1",
          organization_id: "org-1",
          project_id: null,
          template_id: "t1",
          name: "Weekly infra summary",
          description: "A weekly rundown of infrastructure health.",
          category: "infrastructure",
          report_type: "summary",
          default_format: "pdf",
          parameter_values: {},
          filters: [],
          enabled: true,
          owner_id: null,
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
      <ReportDetailPage reportId="r1" />
    </QueryClientProvider>,
  );
}

describe("ReportDetailPage", () => {
  afterEach(() => {
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("loads the real report and renders its identity and description", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Weekly infra summary" })).toBeInTheDocument());
    expect(screen.getByText("A weekly rundown of infrastructure health.")).toBeInTheDocument();
    expect(screen.getByText("infrastructure")).toBeInTheDocument();
  });

  it("navigates back to the Reports list", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Back to Reports" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Back to Reports" }));

    expect(push).toHaveBeenCalledWith("/reporting/reports");
  });
});
