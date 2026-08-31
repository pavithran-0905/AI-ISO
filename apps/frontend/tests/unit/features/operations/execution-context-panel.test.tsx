import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExecutionContextPanel } from "@/features/operations/components/execution-context-panel";
import type { AutomationExecution } from "@/features/automation/types";

const EXECUTION: AutomationExecution = {
  id: "exec-1",
  organizationId: "org-1",
  jobId: "job-1",
  executionPlanId: null,
  status: "failed",
  executionMode: "manual",
  triggeredBy: "user-1",
  variables: { _target_ids: ["asset-1", "asset-2"], region: "us-east-1" },
  startedAt: "2026-08-01T10:00:00Z",
  completedAt: "2026-08-01T10:05:00Z",
  timeoutSeconds: null,
  errorMessage: "Connection refused",
  createdAt: "2026-08-01T09:59:00Z",
};

describe("ExecutionContextPanel", () => {
  it("shows the execution's own real identity, status, and error", () => {
    render(<ExecutionContextPanel execution={EXECUTION} />);
    expect(screen.getByText(/Run exec-1/)).toBeInTheDocument();
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Execution" })).toHaveAttribute("href", "/automation/executions/exec-1");
  });

  it("shows real target ids as plain, unlinked identifiers — never a fabricated resource link", () => {
    render(<ExecutionContextPanel execution={EXECUTION} />);
    expect(screen.getByText("asset-1")).toBeInTheDocument();
    expect(screen.getByText("asset-2")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /asset-1/ })).not.toBeInTheDocument();
  });

  it("shows a plain message when the run had no targets", () => {
    render(<ExecutionContextPanel execution={{ ...EXECUTION, variables: {} }} />);
    expect(screen.getByText(/executed on the AI-IOS automation host/)).toBeInTheDocument();
  });

  it("offers Ask AI referencing the real execution id and error", () => {
    render(<ExecutionContextPanel execution={EXECUTION} />);
    const askAi = screen.getByRole("link", { name: /Ask AI/ });
    const decoded = decodeURIComponent(askAi.getAttribute("href") ?? "");
    expect(decoded).toContain("exec-1");
    expect(decoded).toContain("Connection refused");
  });
});
