import { afterEach, describe, expect, it, vi } from "vitest";

import { reportsApi } from "@/features/reporting/api/reports-api";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.resolve(body) }));
}

describe("reportsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps ReportResponse's real snake_case fields to the domain shape, filters included", async () => {
    mockFetchOnce(
      envelope({
        id: "r1",
        organization_id: "org-1",
        project_id: null,
        template_id: "t1",
        name: "Weekly infra summary",
        description: "d",
        category: "infrastructure",
        report_type: "summary",
        default_format: "pdf",
        parameter_values: { region: "us-east" },
        filters: [{ field: "status", operator: "eq", value: "open" }],
        enabled: true,
        owner_id: "u1",
      }),
    );

    const report = await reportsApi.getById("r1");

    expect(report.templateId).toBe("t1");
    expect(report.defaultFormat).toBe("pdf");
    expect(report.filters).toEqual([{ field: "status", operator: "eq", value: "open" }]);
    expect(report.parameterValues).toEqual({ region: "us-east" });
  });

  it("builds the list query from only the real GET /reports params — organization_id, category, enabled_only", async () => {
    mockFetchOnce(envelope([]));

    await reportsApi.list({ organizationId: "org-1", category: "compliance", enabledOnly: true });

    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(url).toContain("organization_id=org-1");
    expect(url).toContain("category=compliance");
    expect(url).toContain("enabled_only=true");
  });

  it("treats generate as synchronous, returning the complete execution+exports result", async () => {
    mockFetchOnce(
      envelope({
        execution: {
          id: "e1",
          job_id: "r1",
          schedule_id: null,
          status: "succeeded",
          row_count: 12,
          section_count: 3,
          duration_ms: 842.5,
          error_message: null,
          triggered_by: "u1",
          started_at: "2026-01-01T00:00:00Z",
          finished_at: "2026-01-01T00:00:01Z",
        },
        exports: [
          {
            id: "x1",
            execution_id: "e1",
            export_format: "pdf",
            filename: "report.pdf",
            content_type: "application/pdf",
            size_bytes: 1024,
            checksum_sha256: "abc",
            download_count: 0,
          },
        ],
        degraded_sections: ["ai_summary"],
        distributions: [],
        archive_id: null,
      }),
    );

    const result = await reportsApi.generate({ reportId: "r1" });

    expect(result.execution.status).toBe("succeeded");
    expect(result.degradedSections).toEqual(["ai_summary"]);
    expect(result.exports[0]?.filename).toBe("report.pdf");
  });
});
