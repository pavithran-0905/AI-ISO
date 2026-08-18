import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunAutomationDialog } from "@/features/automation/components/run-automation-dialog";
import type { AutomationJob } from "@/features/automation/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

const JOB: AutomationJob = {
  id: "j1",
  organizationId: "org-1",
  projectId: null,
  name: "Patch web fleet",
  description: null,
  automationType: "patch_management",
  playbookType: "shell_script",
  status: "active",
  executionMode: "manual",
  content: "echo hi",
  targetSelector: {},
  variables: { region: "us-east" },
  tags: [],
  timeoutSeconds: null,
  ownerId: null,
};

function renderDialog(job: AutomationJob = JOB) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RunAutomationDialog job={job} open onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("RunAutomationDialog", () => {
  afterEach(() => {
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("requires an explicit Review step before the run can be confirmed — the confirm button never appears on step one", () => {
    renderDialog();

    expect(screen.queryByRole("button", { name: "Run Automation" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review" })).toBeInTheDocument();
  });

  it("shows a real confirmation summary naming the automation and its variables before running", () => {
    renderDialog();

    fireEvent.click(screen.getByRole("button", { name: "Review" }));

    expect(screen.getByRole("heading", { name: "Confirm this run" })).toBeInTheDocument();
    expect(screen.getByText("Patch web fleet")).toBeInTheDocument();
    expect(screen.getByText("region")).toBeInTheDocument();
    expect(screen.getByText("us-east")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Automation" })).toBeInTheDocument();
  });

  it("warns when the automation's playbook type can't actually be dispatched", () => {
    renderDialog({ ...JOB, playbookType: "tosca_service_template" });

    expect(screen.getByText(/can't be executed yet/)).toBeInTheDocument();
  });

  it("waits for the real backend response, then navigates to the new execution", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 201,
        ok: true,
        json: () =>
          Promise.resolve(
            envelope({
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
            }),
          ),
      }),
    );
    renderDialog();

    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    fireEvent.click(screen.getByRole("button", { name: "Run Automation" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/automation/executions/e1"));
  });
});
