import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OperationsWorkspacePage } from "@/features/operations/pages/operations-workspace-page";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import { useAuditEvents } from "@/features/audit/hooks/use-audit";
import { useSelectedOrganization } from "@/organization/use-organizations";
import type { Alert } from "@/features/alerting/types";
import type { AutomationExecution } from "@/features/automation/types";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/operations",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));
vi.mock("@/features/alerting/hooks/use-alerts", () => ({ useAlerts: vi.fn() }));
vi.mock("@/features/automation/hooks/use-executions", () => ({ useExecutions: vi.fn() }));
vi.mock("@/features/audit/hooks/use-audit", () => ({ useAuditEvents: vi.fn() }));
vi.mock("@/organization/use-organizations", () => ({ useSelectedOrganization: vi.fn() }));
vi.mock("@/features/alerting/components/alert-actions", () => ({ AlertActions: () => <div>AlertActions</div> }));
vi.mock("@/features/alerting/components/alert-correlations-list", () => ({ AlertCorrelationsList: () => <div>AlertCorrelationsList</div> }));
vi.mock("@/features/alerting/components/alert-lifecycle-timeline", () => ({ AlertLifecycleTimeline: () => <div>AlertLifecycleTimeline</div> }));

const ALERT: Alert = {
  id: "a1",
  organizationId: "org-1",
  projectId: null,
  ruleId: null,
  source: "monitoring",
  severity: "critical",
  status: "open",
  title: "CPU threshold exceeded",
  message: "CPU above 90%",
  fingerprint: "f1",
  sourceReference: {},
  assignedTo: null,
  triggeredAt: "2026-08-01T10:00:00Z",
  resolvedAt: null,
  closedAt: null,
};

const EXECUTION: AutomationExecution = {
  id: "exec-1",
  organizationId: "org-1",
  jobId: "job-1",
  executionPlanId: null,
  status: "completed",
  executionMode: "manual",
  triggeredBy: "user-1",
  variables: {},
  startedAt: "2026-08-01T10:00:00Z",
  completedAt: "2026-08-01T10:05:00Z",
  timeoutSeconds: null,
  errorMessage: null,
  createdAt: "2026-08-01T09:59:00Z",
};

function mockCommon(alerts: Alert[] = [], executions: AutomationExecution[] = []) {
  vi.mocked(useSelectedOrganization).mockReturnValue({
    organizations: undefined,
    isLoading: false,
    isError: false,
    error: null,
    selectedOrganizationId: "org-1",
    needsSelection: false,
    hasNoAccess: false,
  });
  vi.mocked(useAlerts).mockReturnValue({ data: alerts, isLoading: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof useAlerts>);
  vi.mocked(useExecutions).mockReturnValue({ data: executions, isLoading: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof useExecutions>);
  vi.mocked(useAuditEvents).mockReturnValue({
    data: { items: [], offset: 0, limit: 8, hasMore: false },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useAuditEvents>);
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <OperationsWorkspacePage />
    </QueryClientProvider>,
  );
}

describe("OperationsWorkspacePage", () => {
  afterEach(() => {
    push.mockClear();
    mockSearch.current = "";
  });

  it("shows a calm no-signal state when the scope is healthy", () => {
    mockCommon([], []);
    renderPage();
    expect(screen.getByText("No active issues detected in this scope")).toBeInTheDocument();
  });

  it("shows nothing selected by default in the investigation panel", () => {
    mockCommon([ALERT], [EXECUTION]);
    renderPage();
    expect(screen.getByText("Nothing selected")).toBeInTheDocument();
  });

  it("selecting an alert pushes a URL that identifies it by type and id", () => {
    mockCommon([ALERT], []);
    renderPage();

    fireEvent.click(screen.getByText("CPU threshold exceeded"));
    expect(push).toHaveBeenCalledWith("/operations?signal=alert%3Aa1");
  });

  it("restores the selected alert from the URL on load — a shareable investigation context", () => {
    mockSearch.current = "signal=alert:a1";
    mockCommon([ALERT], []);
    renderPage();

    expect(screen.getByText("AlertActions")).toBeInTheDocument();
    expect(screen.getByText("AlertCorrelationsList")).toBeInTheDocument();
    expect(screen.queryByText("Nothing selected")).not.toBeInTheDocument();
  });

  it("restores a selected execution from the URL, distinct from an alert selection", () => {
    mockSearch.current = "signal=execution:exec-1";
    mockCommon([], [EXECUTION]);
    renderPage();

    expect(screen.getByRole("link", { name: "Open Execution" })).toHaveAttribute("href", "/automation/executions/exec-1");
  });

  it("offers Investigate with AI summarizing only real, already-loaded counts", () => {
    mockCommon([ALERT], []);
    renderPage();

    const askAi = screen.getByRole("link", { name: /Ask AI/ });
    const decoded = decodeURIComponent(askAi.getAttribute("href") ?? "");
    expect(decoded).toContain("1 active alert");
    expect(decoded).toContain("critical");
  });
});
