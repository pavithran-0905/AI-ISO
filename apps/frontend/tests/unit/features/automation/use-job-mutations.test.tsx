import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useCancelAutomation, useCreateAutomationJob, useRunAutomation } from "@/features/automation/hooks/use-jobs";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function errorEnvelope(message = "No active execution for this job") {
  return { success: false, message, error: { code: "AIIOS-AUTOMATION-0001", details: [] }, meta: {} };
}

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }));
}

function jobBody() {
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
    variables: {},
    tags: [],
    timeout_seconds: null,
    owner_id: null,
  };
}

function executionBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "e1",
    organization_id: "org-1",
    job_id: "j1",
    execution_plan_id: null,
    status: "pending",
    execution_mode: "immediate",
    triggered_by: "u1",
    variables: {},
    started_at: null,
    completed_at: null,
    timeout_seconds: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("automation job mutation hooks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("useCreateAutomationJob waits for the real backend response before succeeding", async () => {
    mockFetchOnce(201, envelope(jobBody()));

    const { result } = renderHook(() => useCreateAutomationJob(), { wrapper });
    result.current.mutate({
      organizationId: "org-1",
      name: "Patch web fleet",
      automationType: "patch_management",
      playbookType: "shell_script",
      executionMode: "manual",
      content: "echo hi",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/automation/jobs"), expect.objectContaining({ method: "POST" }));
  });

  it("useRunAutomation returns a pending execution — the real run happens on a worker", async () => {
    mockFetchOnce(201, envelope(executionBody()));

    const { result } = renderHook(() => useRunAutomation("j1"), { wrapper });
    result.current.mutate({ variables: { region: "us-east" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("pending");
  });

  it("useCancelAutomation surfaces a rejected mutation without pretending the run was cancelled", async () => {
    mockFetchOnce(404, errorEnvelope());

    const { result } = renderHook(() => useCancelAutomation(), { wrapper });
    result.current.mutate("j1");

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.isSuccess).toBe(false);
  });
});
