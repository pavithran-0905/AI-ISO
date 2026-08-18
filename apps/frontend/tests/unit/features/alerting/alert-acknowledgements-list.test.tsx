import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertAcknowledgementsList } from "@/features/alerting/components/alert-acknowledgements-list";
import { useAlertAcknowledgements } from "@/features/alerting/hooks/use-alert-acknowledgements";

vi.mock("@/features/alerting/hooks/use-alert-acknowledgements", () => ({ useAlertAcknowledgements: vi.fn() }));

const mocked = vi.mocked(useAlertAcknowledgements);

describe("AlertAcknowledgementsList", () => {
  it("renders each real acknowledgement row, not a single field", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: "ack-1",
          alertId: "a1",
          acknowledgementType: "manual",
          acknowledgedBy: "user-1",
          comment: "Looking into it",
          resolutionNotes: null,
          acknowledgedAt: "2026-01-01T00:00:00Z",
        },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertAcknowledgements>);

    render(<AlertAcknowledgementsList alertId="a1" />);

    expect(screen.getByText(/user-1/)).toBeInTheDocument();
    expect(screen.getByText("Looking into it")).toBeInTheDocument();
  });

  it("shows an honest empty state when no one has acknowledged this alert", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertAcknowledgements>);

    render(<AlertAcknowledgementsList alertId="a1" />);

    expect(screen.getByText("No acknowledgements yet")).toBeInTheDocument();
  });
});
