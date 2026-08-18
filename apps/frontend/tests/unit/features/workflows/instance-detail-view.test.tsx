import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InstanceDetailView } from "@/features/workflows/components/instance-detail-view";
import {
  useDecideApproval,
  useInstanceApprovals,
  useInstanceLogs,
  useInstanceSteps,
  useWorkflow,
} from "@/features/workflows/hooks/use-workflows";
import type { WorkflowInstance } from "@/features/workflows/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

vi.mock("@/features/workflows/hooks/use-workflows", () => ({
  useWorkflow: vi.fn(),
  useInstanceSteps: vi.fn(),
  useInstanceLogs: vi.fn(),
  useInstanceApprovals: vi.fn(),
  useDecideApproval: vi.fn(),
}));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

const mockedWorkflow = vi.mocked(useWorkflow);
const mockedSteps = vi.mocked(useInstanceSteps);
const mockedLogs = vi.mocked(useInstanceLogs);
const mockedApprovals = vi.mocked(useInstanceApprovals);
const mockedDecide = vi.mocked(useDecideApproval);
const mockedPermissions = vi.mocked(usePermissions);

const INSTANCE: WorkflowInstance = {
  id: "i1",
  organizationId: "org-1",
  projectId: null,
  definitionId: "w1",
  versionId: "v1",
  parentInstanceId: null,
  sdkExecutionId: null,
  status: "waiting",
  triggerType: "manual",
  triggeredBy: "u1",
  startedAt: "2026-01-01T00:00:00Z",
  finishedAt: null,
  errorMessage: null,
};

function emptyQuery(data: unknown[] = []) {
  return { isLoading: false, isError: false, data, error: null, refetch: vi.fn() } as unknown;
}

function renderView() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <InstanceDetailView instance={INSTANCE} />
    </QueryClientProvider>,
  );
}

describe("InstanceDetailView approvals", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("only offers a decision to an approver who can approve, and requires a name before deciding", async () => {
    mockedWorkflow.mockReturnValue(emptyQuery() as ReturnType<typeof useWorkflow>);
    mockedSteps.mockReturnValue(emptyQuery() as ReturnType<typeof useInstanceSteps>);
    mockedLogs.mockReturnValue(emptyQuery() as ReturnType<typeof useInstanceLogs>);
    mockedApprovals.mockReturnValue(
      emptyQuery([
        {
          id: "a1",
          instanceId: "i1",
          nodeId: "manual-review",
          nodeType: "approval",
          approvers: ["ops-lead"],
          requiredApprovals: 1,
          decision: "pending",
          decisionsByApprover: {},
          comments: null,
          escalatedTo: null,
          timeoutSeconds: 3600,
          decidedAt: null,
        },
      ]) as ReturnType<typeof useInstanceApprovals>,
    );
    const decideMock = vi.fn();
    mockedDecide.mockReturnValue({ mutateAsync: decideMock, isPending: false } as unknown as ReturnType<typeof useDecideApproval>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderView();

    expect(screen.getByText("manual-review")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(decideMock).not.toHaveBeenCalled();
    expect(toast.danger).toHaveBeenCalledWith("Who is approving?", expect.any(String));
  });

  it("records a real decision once an approver name is entered", async () => {
    mockedWorkflow.mockReturnValue(emptyQuery() as ReturnType<typeof useWorkflow>);
    mockedSteps.mockReturnValue(emptyQuery() as ReturnType<typeof useInstanceSteps>);
    mockedLogs.mockReturnValue(emptyQuery() as ReturnType<typeof useInstanceLogs>);
    mockedApprovals.mockReturnValue(
      emptyQuery([
        {
          id: "a1",
          instanceId: "i1",
          nodeId: "manual-review",
          nodeType: "approval",
          approvers: ["ops-lead"],
          requiredApprovals: 1,
          decision: "pending",
          decisionsByApprover: {},
          comments: null,
          escalatedTo: null,
          timeoutSeconds: 3600,
          decidedAt: null,
        },
      ]) as ReturnType<typeof useInstanceApprovals>,
    );
    const decideMock = vi.fn().mockResolvedValue({});
    mockedDecide.mockReturnValue({ mutateAsync: decideMock, isPending: false } as unknown as ReturnType<typeof useDecideApproval>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderView();

    fireEvent.change(screen.getByLabelText("Your approver name"), { target: { value: "ops-lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(decideMock).toHaveBeenCalledWith({ approvalId: "a1", input: { approver: "ops-lead", approve: true, comments: undefined } }));
  });

  it("does not offer a decision form when the capability model disallows approving", () => {
    mockedWorkflow.mockReturnValue(emptyQuery() as ReturnType<typeof useWorkflow>);
    mockedSteps.mockReturnValue(emptyQuery() as ReturnType<typeof useInstanceSteps>);
    mockedLogs.mockReturnValue(emptyQuery() as ReturnType<typeof useInstanceLogs>);
    mockedApprovals.mockReturnValue(
      emptyQuery([
        {
          id: "a1",
          instanceId: "i1",
          nodeId: "manual-review",
          nodeType: "approval",
          approvers: ["ops-lead"],
          requiredApprovals: 1,
          decision: "pending",
          decisionsByApprover: {},
          comments: null,
          escalatedTo: null,
          timeoutSeconds: 3600,
          decidedAt: null,
        },
      ]) as ReturnType<typeof useInstanceApprovals>,
    );
    mockedDecide.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDecideApproval>);
    mockedPermissions.mockReturnValue({ role: "viewer", can: () => false, isReadOnly: true, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderView();

    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });
});
