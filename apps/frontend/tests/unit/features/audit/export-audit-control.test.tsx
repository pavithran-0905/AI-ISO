import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExportAuditControl } from "@/features/audit/components/export-audit-control";
import { useExportComplianceAudit } from "@/features/audit/hooks/use-audit";

vi.mock("@/features/audit/hooks/use-audit", () => ({ useExportComplianceAudit: vi.fn() }));

describe("ExportAuditControl", () => {
  it("triggers the real compliance report pipeline with the chosen format and organization", () => {
    const mutate = vi.fn();
    vi.mocked(useExportComplianceAudit).mockReturnValue({ mutate, isPending: false, isError: false } as unknown as ReturnType<typeof useExportComplianceAudit>);

    render(<ExportAuditControl organizationId="org-1" />);
    fireEvent.change(screen.getByLabelText("Export format"), { target: { value: "json" } });
    fireEvent.click(screen.getByRole("button", { name: /Export last 90 days/ }));

    expect(mutate).toHaveBeenCalledWith({ organizationId: "org-1", reportFormat: "json", periodDays: 90 });
  });

  it("shows the backend's real error message when report generation fails", () => {
    vi.mocked(useExportComplianceAudit).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error("Report generation ended with status \"failed\"."),
    } as unknown as ReturnType<typeof useExportComplianceAudit>);

    render(<ExportAuditControl organizationId="org-1" />);
    expect(screen.getByText("Report generation ended with status \"failed\".")).toBeInTheDocument();
  });

  it("disables the export button while the mutation is pending", () => {
    vi.mocked(useExportComplianceAudit).mockReturnValue({ mutate: vi.fn(), isPending: true, isError: false } as unknown as ReturnType<typeof useExportComplianceAudit>);
    render(<ExportAuditControl organizationId="org-1" />);
    expect(screen.getByRole("button", { name: /Export last 90 days/ })).toBeDisabled();
  });
});
