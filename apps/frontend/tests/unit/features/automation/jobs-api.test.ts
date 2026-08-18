import { afterEach, describe, expect, it, vi } from "vitest";

import { jobsApi } from "@/features/automation/api/jobs-api";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.resolve(body) }));
}

function jobBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "j1",
    organization_id: "org-1",
    project_id: null,
    name: "Patch web fleet",
    description: null,
    automation_type: "patch_management",
    playbook_type: "shell_script",
    status: "active",
    execution_mode: "manual",
    content: "echo hi",
    target_selector: {},
    variables: { region: "us-east" },
    tags: ["prod"],
    timeout_seconds: 300,
    owner_id: null,
    ...overrides,
  };
}

describe("jobsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps AutomationJobResponse's real snake_case fields to the domain shape", async () => {
    mockFetchOnce(envelope(jobBody()));

    const job = await jobsApi.getById("j1");

    expect(job.automationType).toBe("patch_management");
    expect(job.playbookType).toBe("shell_script");
    expect(job.variables).toEqual({ region: "us-east" });
  });

  it("builds the list query from the one real GET /automation/jobs param", async () => {
    mockFetchOnce(envelope([]));

    await jobsApi.list("org-1");

    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(url).toContain("organization_id=org-1");
  });

  it("sends every field on update, including status, since PUT is a full replace", async () => {
    mockFetchOnce(envelope(jobBody({ status: "disabled" })));

    await jobsApi.update("j1", {
      name: "Patch web fleet",
      description: null,
      status: "disabled",
      automationType: "patch_management",
      playbookType: "shell_script",
      executionMode: "manual",
      content: "echo hi",
      targetSelector: {},
      variables: {},
      tags: [],
      timeoutSeconds: null,
      ownerId: null,
    });

    const [, options] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const sentBody = JSON.parse(options.body as string);
    expect(sentBody.status).toBe("disabled");
    expect(options.method).toBe("PUT");
  });

  it("run posts target_ids and variables to the real execute endpoint", async () => {
    mockFetchOnce(
      envelope({
        id: "e1",
        organization_id: "org-1",
        job_id: "j1",
        execution_plan_id: null,
        status: "pending",
        execution_mode: "immediate",
        triggered_by: "u1",
        variables: { region: "us-east", _target_ids: ["t1"] },
        started_at: null,
        completed_at: null,
        timeout_seconds: null,
        error_message: null,
        created_at: "2026-01-01T00:00:00Z",
      }),
    );

    const execution = await jobsApi.run("j1", { targetIds: ["t1"], variables: { region: "us-east" } });

    expect(execution.status).toBe("pending");
    const [url, options] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/automation/jobs/j1/execute");
    expect(JSON.parse(options.body as string)).toMatchObject({ target_ids: ["t1"] });
  });
});
