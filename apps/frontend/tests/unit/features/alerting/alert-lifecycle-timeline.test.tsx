import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertLifecycleTimeline } from "@/features/alerting/components/alert-lifecycle-timeline";
import { useAlertHistory } from "@/features/alerting/hooks/use-alert-history";

vi.mock("@/features/alerting/hooks/use-alert-history", () => ({ useAlertHistory: vi.fn() }));

const mocked = vi.mocked(useAlertHistory);

describe("AlertLifecycleTimeline", () => {
  it("renders real status transitions, most recent first", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { id: "h1", alertId: "a1", fromStatus: null, toStatus: "open", changedBy: null, reason: null, changedAt: "2026-01-01T00:00:00Z" },
        {
          id: "h2",
          alertId: "a1",
          fromStatus: "open",
          toStatus: "acknowledged",
          changedBy: "user-1",
          reason: "picked up",
          changedAt: "2026-01-02T00:00:00Z",
        },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertHistory>);

    render(<AlertLifecycleTimeline alertId="a1" />);

    const entries = screen.getAllByText(/→|open/);
    expect(entries[0]).toHaveTextContent("open → acknowledged");
    expect(screen.getByText(/picked up/)).toBeInTheDocument();
  });

  it("shows an honest empty state when there's no history yet", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertHistory>);

    render(<AlertLifecycleTimeline alertId="a1" />);

    expect(screen.getByText("No history yet")).toBeInTheDocument();
  });
});
