import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertActions } from "@/features/alerting/components/alert-actions";
import { useAcknowledgeAlert } from "@/features/alerting/hooks/use-acknowledge-alert";
import { useCloseAlert } from "@/features/alerting/hooks/use-close-alert";
import { useEscalateAlert } from "@/features/alerting/hooks/use-escalate-alert";
import { useResolveAlert } from "@/features/alerting/hooks/use-resolve-alert";
import type { Alert } from "@/features/alerting/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

vi.mock("@/features/alerting/hooks/use-acknowledge-alert", () => ({ useAcknowledgeAlert: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-resolve-alert", () => ({ useResolveAlert: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-escalate-alert", () => ({ useEscalateAlert: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-close-alert", () => ({ useCloseAlert: vi.fn() }));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

const mockedAcknowledge = vi.mocked(useAcknowledgeAlert);
const mockedResolve = vi.mocked(useResolveAlert);
const mockedEscalate = vi.mocked(useEscalateAlert);
const mockedClose = vi.mocked(useCloseAlert);
const mockedPermissions = vi.mocked(usePermissions);

const ALERT: Alert = {
  id: "a1",
  organizationId: "org-1",
  projectId: null,
  ruleId: null,
  source: "monitoring",
  severity: "high",
  status: "open",
  title: "Something happened",
  message: "",
  fingerprint: "fp-1",
  sourceReference: {},
  assignedTo: null,
  triggeredAt: "2026-01-01T00:00:00Z",
  resolvedAt: null,
  closedAt: null,
};

function mutationReturn(overrides: Record<string, unknown> = {}) {
  return {
    mutateAsync: vi.fn().mockResolvedValue(ALERT),
    isPending: false,
    isSuccess: false,
    isError: false,
    ...overrides,
  };
}

describe("AlertActions", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function setup(mutations: {
    acknowledge?: ReturnType<typeof mutationReturn>;
    resolve?: ReturnType<typeof mutationReturn>;
    escalate?: ReturnType<typeof mutationReturn>;
    close?: ReturnType<typeof mutationReturn>;
  } = {}) {
    mockedAcknowledge.mockReturnValue((mutations.acknowledge ?? mutationReturn()) as unknown as ReturnType<typeof useAcknowledgeAlert>);
    mockedResolve.mockReturnValue((mutations.resolve ?? mutationReturn()) as unknown as ReturnType<typeof useResolveAlert>);
    mockedEscalate.mockReturnValue((mutations.escalate ?? mutationReturn()) as unknown as ReturnType<typeof useEscalateAlert>);
    mockedClose.mockReturnValue((mutations.close ?? mutationReturn()) as unknown as ReturnType<typeof useCloseAlert>);
    mockedPermissions.mockReturnValue({
      role: "operator",
      can: () => true,
      isReadOnly: false,
      isAdministrative: false,
    } as unknown as ReturnType<typeof usePermissions>);
  }

  it("renders every real mutation as a button when the user can perform them", () => {
    setup();
    render(<AlertActions alert={ALERT} />);

    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Escalate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("hides every action once the alert is resolved — no backend Reopen route exists", () => {
    setup();
    render(<AlertActions alert={{ ...ALERT, status: "resolved" }} />);

    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
  });

  it("hides only the actions the coarse capability model disallows", () => {
    mockedPermissions.mockReturnValue({
      role: "operator",
      can: (action: string) => action === "update",
      isReadOnly: false,
      isAdministrative: false,
    } as unknown as ReturnType<typeof usePermissions>);
    mockedAcknowledge.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useAcknowledgeAlert>);
    mockedResolve.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useResolveAlert>);
    mockedEscalate.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useEscalateAlert>);
    mockedClose.mockReturnValue(mutationReturn() as unknown as ReturnType<typeof useCloseAlert>);

    render(<AlertActions alert={ALERT} />);

    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Escalate" })).not.toBeInTheDocument();
  });

  it("waits for the confirmed backend response before reporting success, then closes the dialog", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(ALERT);
    setup({ acknowledge: mutationReturn({ mutateAsync }) });
    render(<AlertActions alert={ALERT} />);

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Acknowledge alert" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Comment (optional)"), { target: { value: "on it" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Acknowledge" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith("on it"));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Alert acknowledged"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("reports failure via toast without closing the flow silently", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("backend rejected"));
    setup({ resolve: mutationReturn({ mutateAsync }) });
    render(<AlertActions alert={ALERT} />);

    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Resolve" }));

    await waitFor(() => expect(toast.danger).toHaveBeenCalledWith("Failed to resolve alert", "Please try again."));
  });

  it("disables every action button while a mutation is pending, preventing duplicate submission", () => {
    setup({ acknowledge: mutationReturn({ isPending: true }) });
    render(<AlertActions alert={ALERT} />);

    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resolve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Escalate" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
  });
});
