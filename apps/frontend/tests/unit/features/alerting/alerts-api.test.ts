import { afterEach, describe, expect, it, vi } from "vitest";

import { alertsApi } from "@/features/alerting/api/alerts-api";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.resolve(body) }));
}

describe("alertsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps AlertResponse's real field shape, including the non-nullable fingerprint and object-typed source_reference", async () => {
    mockFetchOnce(
      envelope({
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
      }),
    );

    const alert = await alertsApi.getById("a1");

    expect(alert.fingerprint).toBe("fp-1");
    expect(alert.sourceReference).toEqual({ host: "db-01" });
  });

  it("builds the list query from only the real GET /alerts params — organization_id, status, severity", async () => {
    mockFetchOnce(envelope([]));

    await alertsApi.list({ organizationId: "org-1", status: "open", severity: "high" });

    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(url).toContain("organization_id=org-1");
    expect(url).toContain("status=open");
    expect(url).toContain("severity=high");
  });

  it("treats DELETE /alerts/{id} as the real status-transition-to-closed route", async () => {
    mockFetchOnce(
      envelope({
        id: "a1",
        organization_id: "org-1",
        project_id: null,
        rule_id: null,
        source: "monitoring",
        severity: "low",
        status: "closed",
        title: "t",
        message: "m",
        fingerprint: "fp-1",
        source_reference: {},
        assigned_to: null,
        triggered_at: "2026-01-01T00:00:00Z",
        resolved_at: null,
        closed_at: "2026-01-02T00:00:00Z",
      }),
    );

    const alert = await alertsApi.close("a1");

    expect(alert.status).toBe("closed");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]).toMatchObject({ method: "DELETE" });
  });
});
