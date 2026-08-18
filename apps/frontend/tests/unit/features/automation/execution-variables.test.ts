import { describe, expect, it } from "vitest";

import { splitExecutionVariables } from "@/features/automation/lib/execution-variables";
import type { AutomationExecution } from "@/features/automation/types";

function execution(variables: Record<string, unknown>): AutomationExecution {
  return {
    id: "e1",
    organizationId: "org-1",
    jobId: "j1",
    executionPlanId: null,
    status: "completed",
    executionMode: "immediate",
    triggeredBy: "u1",
    variables,
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: "2026-01-01T00:05:00Z",
    timeoutSeconds: null,
    errorMessage: null,
    createdAt: "2026-01-01T00:00:00Z",
  };
}

describe("splitExecutionVariables", () => {
  it("separates the backend's internal _target_ids key from the operator's own variables", () => {
    const { variables, targetIds } = splitExecutionVariables(execution({ region: "us-east", _target_ids: ["t1", "t2"] }));

    expect(variables).toEqual({ region: "us-east" });
    expect(targetIds).toEqual(["t1", "t2"]);
  });

  it("returns an empty targetIds array when the run had no targets", () => {
    const { variables, targetIds } = splitExecutionVariables(execution({ region: "us-east" }));

    expect(variables).toEqual({ region: "us-east" });
    expect(targetIds).toEqual([]);
  });
});
