import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { JobActions } from "@/features/automation/components/job-actions";
import {
  useCancelAutomation,
  useDeleteAutomationJob,
  usePauseAutomation,
  useResumeAutomation,
} from "@/features/automation/hooks/use-jobs";
import type { AutomationJob } from "@/features/automation/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/features/automation/hooks/use-jobs", async () => {
  const actual = await vi.importActual<typeof import("@/features/automation/hooks/use-jobs")>("@/features/automation/hooks/use-jobs");
  return { ...actual, useCancelAutomation: vi.fn(), usePauseAutomation: vi.fn(), useResumeAutomation: vi.fn(), useDeleteAutomationJob: vi.fn() };
});
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

const mockedCancel = vi.mocked(useCancelAutomation);
const mockedPause = vi.mocked(usePauseAutomation);
const mockedResume = vi.mocked(useResumeAutomation);
const mockedDelete = vi.mocked(useDeleteAutomationJob);
const mockedPermissions = vi.mocked(usePermissions);

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
  variables: {},
  tags: [],
  timeoutSeconds: null,
  ownerId: null,
};

function mutationReturn(overrides: Record<string, unknown> = {}) {
  return { mutateAsync: vi.fn().mockResolvedValue(JOB), isPending: false, ...overrides };
}

describe("JobActions", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function setup() {
    mockedCancel.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useCancelAutomation>);
    mockedPause.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof usePauseAutomation>);
    mockedResume.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useResumeAutomation>);
    mockedDelete.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useDeleteAutomationJob>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);
  }

  it("does not show 'Cancelled' until the backend confirms it — cancel requires a separate confirmation step", () => {
    setup();
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JobActions job={JOB} /></QueryClientProvider>);

    fireEvent.click(screen.getByRole("button", { name: /Cancel run/ }));

    expect(screen.getByRole("heading", { name: /Cancel the running/ })).toBeInTheDocument();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("reports a resuming run honestly — the backend response still says paused until a worker picks it up", async () => {
    setup();
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JobActions job={JOB} /></QueryClientProvider>);

    fireEvent.click(screen.getByRole("button", { name: "Resume run" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Resuming run", expect.stringContaining("running once a worker")));
  });

  it("surfaces the backend's real error message on a failed cancel, not a generic failure", async () => {
    const { ApiRequestError } = await import("@/api/client");
    mockedCancel.mockReturnValue(
      mutationReturn({ mutateAsync: vi.fn().mockRejectedValue(new ApiRequestError(404, "No active execution for this job", "AIIOS-AUTOMATION-0001", [])) }) as unknown as ReturnType<
        typeof useCancelAutomation
      >,
    );
    mockedPause.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof usePauseAutomation>);
    mockedResume.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useResumeAutomation>);
    mockedDelete.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useDeleteAutomationJob>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JobActions job={JOB} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: /Cancel run/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel run" }));

    await waitFor(() =>
      expect(toast.danger).toHaveBeenCalledWith("Could not cancel this automation", "No active execution for this job"),
    );
  });

  it("hides mutation actions the coarse capability model disallows", () => {
    mockedCancel.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useCancelAutomation>);
    mockedPause.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof usePauseAutomation>);
    mockedResume.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useResumeAutomation>);
    mockedDelete.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useDeleteAutomationJob>);
    mockedPermissions.mockReturnValue({ role: "viewer", can: () => false, isReadOnly: true, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JobActions job={JOB} /></QueryClientProvider>);

    expect(screen.queryByRole("button", { name: /Run Automation/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delete/ })).not.toBeInTheDocument();
  });
});
