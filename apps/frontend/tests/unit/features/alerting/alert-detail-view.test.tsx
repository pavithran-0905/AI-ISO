import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertDetailView } from "@/features/alerting/components/alert-detail-view";
import { useAcknowledgeAlert } from "@/features/alerting/hooks/use-acknowledge-alert";
import { useAlertAcknowledgements } from "@/features/alerting/hooks/use-alert-acknowledgements";
import { useAlertCorrelations } from "@/features/alerting/hooks/use-alert-correlations";
import { useAlertHistory } from "@/features/alerting/hooks/use-alert-history";
import { useAlertNotifications } from "@/features/alerting/hooks/use-alert-notifications";
import { useCloseAlert } from "@/features/alerting/hooks/use-close-alert";
import { useEscalateAlert } from "@/features/alerting/hooks/use-escalate-alert";
import { useResolveAlert } from "@/features/alerting/hooks/use-resolve-alert";
import type { Alert } from "@/features/alerting/types";
import { usePermissions } from "@/permissions/hooks";

vi.mock("@/features/alerting/hooks/use-alert-history", () => ({ useAlertHistory: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-alert-acknowledgements", () => ({ useAlertAcknowledgements: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-alert-correlations", () => ({ useAlertCorrelations: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-alert-notifications", () => ({ useAlertNotifications: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-acknowledge-alert", () => ({ useAcknowledgeAlert: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-resolve-alert", () => ({ useResolveAlert: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-escalate-alert", () => ({ useEscalateAlert: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-close-alert", () => ({ useCloseAlert: vi.fn() }));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));

function emptyQuery() {
  return { isLoading: false, isError: false, data: [], error: null, refetch: vi.fn() } as unknown;
}

function emptyMutation() {
  return { mutateAsync: vi.fn(), isPending: false, isSuccess: false, isError: false } as unknown;
}

const ALERT: Alert = {
  id: "a1",
  organizationId: "org-1",
  projectId: "proj-1",
  ruleId: null,
  source: "monitoring",
  severity: "critical",
  status: "open",
  title: "Database unreachable",
  message: "Connection refused on primary replica",
  fingerprint: "fp-1",
  sourceReference: { host: "db-01" },
  assignedTo: null,
  triggeredAt: "2026-01-01T00:00:00Z",
  resolvedAt: null,
  closedAt: null,
};

describe("AlertDetailView", () => {
  it("renders the real identity, severity/status, timestamps, and description fields, including raw source reference keys", () => {
    vi.mocked(useAlertHistory).mockReturnValue(emptyQuery() as ReturnType<typeof useAlertHistory>);
    vi.mocked(useAlertAcknowledgements).mockReturnValue(emptyQuery() as ReturnType<typeof useAlertAcknowledgements>);
    vi.mocked(useAlertCorrelations).mockReturnValue(emptyQuery() as ReturnType<typeof useAlertCorrelations>);
    vi.mocked(useAlertNotifications).mockReturnValue(emptyQuery() as ReturnType<typeof useAlertNotifications>);
    vi.mocked(useAcknowledgeAlert).mockReturnValue(emptyMutation() as ReturnType<typeof useAcknowledgeAlert>);
    vi.mocked(useResolveAlert).mockReturnValue(emptyMutation() as ReturnType<typeof useResolveAlert>);
    vi.mocked(useEscalateAlert).mockReturnValue(emptyMutation() as ReturnType<typeof useEscalateAlert>);
    vi.mocked(useCloseAlert).mockReturnValue(emptyMutation() as ReturnType<typeof useCloseAlert>);
    vi.mocked(usePermissions).mockReturnValue({
      role: "operator",
      can: () => true,
      isReadOnly: false,
      isAdministrative: false,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AlertDetailView alert={ALERT} />);

    expect(screen.getByText("Database unreachable")).toBeInTheDocument();
    expect(screen.getByText("Connection refused on primary replica")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("host")).toBeInTheDocument();
    expect(screen.getByText("db-01")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
  });
});
