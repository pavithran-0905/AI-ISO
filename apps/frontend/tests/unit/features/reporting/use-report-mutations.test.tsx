import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useCreateReport, useDeleteReport, useGenerateReport } from "@/features/reporting/hooks/use-reports";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function errorEnvelope() {
  return { success: false, message: "Template is not approved", error: { code: "AIIOS-REPORT-0001", details: [] }, meta: {} };
}

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }));
}

describe("report mutation hooks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("useCreateReport waits for the real backend response before succeeding", async () => {
    mockFetchOnce(
      201,
      envelope({
        id: "r1",
        organization_id: "org-1",
        project_id: null,
        template_id: null,
        name: "New report",
        description: null,
        category: "custom",
        report_type: "custom",
        default_format: "pdf",
        parameter_values: {},
        filters: [],
        enabled: true,
        owner_id: null,
      }),
    );

    const { result } = renderHook(() => useCreateReport(), { wrapper });
    result.current.mutate({ organizationId: "org-1", name: "New report", category: "custom", reportType: "custom" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/reports"), expect.objectContaining({ method: "POST" }));
  });

  it("useGenerateReport surfaces a rejected mutation without pretending a report generated", async () => {
    mockFetchOnce(409, errorEnvelope());

    const { result } = renderHook(() => useGenerateReport(), { wrapper });
    result.current.mutate({ reportId: "r1" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.isSuccess).toBe(false);
  });

  it("useDeleteReport calls the real soft-delete route", async () => {
    mockFetchOnce(200, envelope(null));

    const { result } = renderHook(() => useDeleteReport(), { wrapper });
    result.current.mutate("r1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/reports/r1"), expect.objectContaining({ method: "DELETE" }));
  });
});
