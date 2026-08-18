import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertNotificationsList } from "@/features/alerting/components/alert-notifications-list";
import { useAlertNotifications } from "@/features/alerting/hooks/use-alert-notifications";

vi.mock("@/features/alerting/hooks/use-alert-notifications", () => ({ useAlertNotifications: vi.fn() }));

const mocked = vi.mocked(useAlertNotifications);

describe("AlertNotificationsList", () => {
  it("shows the delivery status and any real error message per notification", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: "n1",
          alertId: "a1",
          routeId: "r1",
          channel: "email",
          status: "failed",
          retryCount: 2,
          errorMessage: "SMTP timeout",
          sentAt: null,
        },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertNotifications>);

    render(<AlertNotificationsList alertId="a1" />);

    expect(screen.getByText("email")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("SMTP timeout")).toBeInTheDocument();
    expect(screen.getByText(/2 retries/)).toBeInTheDocument();
  });

  it("shows an honest empty state when nothing has been sent", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertNotifications>);

    render(<AlertNotificationsList alertId="a1" />);

    expect(screen.getByText("No notifications sent")).toBeInTheDocument();
  });
});
