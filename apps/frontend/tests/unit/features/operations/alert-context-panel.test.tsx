import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertContextPanel } from "@/features/operations/components/alert-context-panel";
import type { Alert } from "@/features/alerting/types";

vi.mock("@/features/alerting/components/alert-actions", () => ({ AlertActions: ({ alert }: { alert: Alert }) => <div>AlertActions:{alert.id}</div> }));
vi.mock("@/features/alerting/components/alert-correlations-list", () => ({ AlertCorrelationsList: ({ alertId }: { alertId: string }) => <div>AlertCorrelationsList:{alertId}</div> }));
vi.mock("@/features/alerting/components/alert-lifecycle-timeline", () => ({ AlertLifecycleTimeline: ({ alertId }: { alertId: string }) => <div>AlertLifecycleTimeline:{alertId}</div> }));

const ALERT: Alert = {
  id: "a1",
  organizationId: "org-1",
  projectId: null,
  ruleId: null,
  source: "monitoring",
  severity: "critical",
  status: "open",
  title: "CPU threshold exceeded",
  message: "CPU usage above 90%.",
  fingerprint: "f1",
  sourceReference: { target_id: "unverified-123" },
  assignedTo: null,
  triggeredAt: "2026-08-01T10:00:00Z",
  resolvedAt: null,
  closedAt: null,
};

describe("AlertContextPanel", () => {
  it("composes the real, existing Alerting components rather than a second alert model", () => {
    render(<AlertContextPanel alert={ALERT} />);

    expect(screen.getByText("AlertActions:a1")).toBeInTheDocument();
    expect(screen.getByText("AlertCorrelationsList:a1")).toBeInTheDocument();
    expect(screen.getByText("AlertLifecycleTimeline:a1")).toBeInTheDocument();
  });

  it("shows the alert's own real fields and a link to its full detail page", () => {
    render(<AlertContextPanel alert={ALERT} />);
    expect(screen.getByText("CPU threshold exceeded")).toBeInTheDocument();
    expect(screen.getByText("CPU usage above 90%.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Alert" })).toHaveAttribute("href", "/alerting/alerts/a1");
  });

  it("never fabricates a resource link from the unstructured source reference", () => {
    render(<AlertContextPanel alert={ALERT} />);
    expect(screen.queryByRole("link", { name: /Open Resource/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/unverified-123/)).not.toBeInTheDocument();
  });

  it("offers Ask AI referencing the real alert", () => {
    render(<AlertContextPanel alert={ALERT} />);
    const askAi = screen.getByRole("link", { name: /Ask AI/ });
    expect(decodeURIComponent(askAi.getAttribute("href") ?? "")).toContain("CPU threshold exceeded");
  });
});
