import { describe, expect, it } from "vitest";

import { executionDurationMs, formatDurationMs } from "@/features/automation/lib/duration";
import type { AutomationExecution } from "@/features/automation/types";

function execution(overrides: Partial<AutomationExecution>): AutomationExecution {
  return {
    id: "e1",
    organizationId: "org-1",
    jobId: "j1",
    executionPlanId: null,
    status: "completed",
    executionMode: "immediate",
    triggeredBy: "u1",
    variables: {},
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: "2026-01-01T00:00:05Z",
    timeoutSeconds: null,
    errorMessage: null,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("executionDurationMs", () => {
  it("computes the real duration from startedAt/completedAt", () => {
    expect(executionDurationMs(execution({}))).toBe(5000);
  });

  it("returns null — not zero — when the run hasn't started", () => {
    expect(executionDurationMs(execution({ startedAt: null, completedAt: null }))).toBeNull();
  });

  it("returns null while the run is still in flight (no completedAt yet)", () => {
    expect(executionDurationMs(execution({ completedAt: null }))).toBeNull();
  });
});

describe("formatDurationMs", () => {
  it("formats sub-minute durations as seconds", () => {
    expect(formatDurationMs(2400)).toBe("2.4s");
  });

  it("formats minute-scale durations", () => {
    expect(formatDurationMs(72_000)).toBe("1m 12s");
  });

  it("passes null through as null for an honest '—' upstream", () => {
    expect(formatDurationMs(null)).toBeNull();
  });
});
