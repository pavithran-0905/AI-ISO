import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GenerationResult } from "@/features/reporting/components/generation-result";
import type { GenerateResult } from "@/features/reporting/types";
import { usePermissions } from "@/permissions/hooks";
import { TestQueryProvider } from "../../../query-test-utils";

vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));

const mockedPermissions = vi.mocked(usePermissions);

const RESULT: GenerateResult = {
  execution: {
    id: "e1",
    jobId: "r1",
    scheduleId: null,
    status: "succeeded",
    rowCount: 42,
    sectionCount: 3,
    durationMs: 1500,
    errorMessage: null,
    triggeredBy: "u1",
    startedAt: "2026-01-01T00:00:00Z",
    finishedAt: "2026-01-01T00:00:02Z",
  },
  exports: [
    { id: "x1", executionId: "e1", exportFormat: "pdf", filename: "report.pdf", contentType: "application/pdf", sizeBytes: 2048, checksumSha256: "abc", downloadCount: 0 },
  ],
  degradedSections: [],
  distributions: [],
  archiveId: null,
};

function renderResult(result: GenerateResult) {
  return render(
    <TestQueryProvider>
      <GenerationResult result={result} />
    </TestQueryProvider>,
  );
}

describe("GenerationResult", () => {
  it("shows the real execution status, counts, and duration", () => {
    mockedPermissions.mockReturnValue({ role: "viewer", can: () => false, isReadOnly: true, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderResult(RESULT);

    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("1.5s")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download/ })).toBeInTheDocument();
  });

  it("shows a real, visible warning for degraded sections instead of a silently-incomplete report", () => {
    mockedPermissions.mockReturnValue({ role: "viewer", can: () => false, isReadOnly: true, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderResult({ ...RESULT, degradedSections: ["ai_summary"] });

    expect(screen.getByText(/Some sections couldn't be resolved/)).toBeInTheDocument();
    expect(screen.getByText(/ai_summary/)).toBeInTheDocument();
  });

  it("shows the real failure message when generation fails", () => {
    mockedPermissions.mockReturnValue({ role: "viewer", can: () => false, isReadOnly: true, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderResult({ ...RESULT, execution: { ...RESULT.execution, status: "failed", errorMessage: "Template is not approved" } });

    expect(screen.getByText("Generation failed")).toBeInTheDocument();
    expect(screen.getByText("Template is not approved")).toBeInTheDocument();
  });

  it("only shows archive/share/distribute actions when the capability model allows export", () => {
    mockedPermissions.mockReturnValue({ role: "operator", can: (action: string) => action === "export", isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    renderResult(RESULT);

    expect(screen.getByRole("button", { name: "Archive this export" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create a share link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Distribute this export" })).toBeInTheDocument();
  });
});
