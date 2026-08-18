import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MaintenanceWindowsList } from "@/features/alerting/components/maintenance-windows-list";
import { useMaintenanceWindows } from "@/features/alerting/hooks/use-maintenance-windows";

vi.mock("@/features/alerting/hooks/use-maintenance-windows", () => ({
  useMaintenanceWindows: vi.fn(),
}));

const mocked = vi.mocked(useMaintenanceWindows);

describe("MaintenanceWindowsList", () => {
  it("renders real maintenance windows, distinguishing enabled from disabled", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: "w1",
          organizationId: "org-1",
          projectId: null,
          name: "Patch window",
          windowType: "recurring",
          scope: "organization",
          scopeReference: null,
          startsAt: "2026-01-01T00:00:00Z",
          endsAt: "2026-01-01T04:00:00Z",
          enabled: true,
        },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useMaintenanceWindows>);

    render(<MaintenanceWindowsList organizationId="org-1" />);

    expect(screen.getByText("Patch window")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
  });

  it("shows an honest empty state when nothing is active", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useMaintenanceWindows>);

    render(<MaintenanceWindowsList organizationId="org-1" />);

    expect(screen.getByText("No active maintenance windows")).toBeInTheDocument();
  });
});
