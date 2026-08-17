import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NotificationArea } from "@/components/navigation/notification-area";

describe("NotificationArea", () => {
  it("shows no unread badge and keeps the panel closed until the bell is clicked", () => {
    render(<NotificationArea />);

    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.queryByText("No notifications yet")).not.toBeInTheDocument();
  });

  it("opens the panel on click and shows the honest empty state (no fabricated notification data)", () => {
    render(<NotificationArea />);

    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("No notifications yet")).toBeInTheDocument();
  });

  it("closes the panel when the bell is clicked again", () => {
    render(<NotificationArea />);
    const bell = screen.getByRole("button", { name: "Notifications" });

    fireEvent.click(bell);
    expect(screen.getByText("No notifications yet")).toBeInTheDocument();

    fireEvent.click(bell);
    expect(screen.queryByText("No notifications yet")).not.toBeInTheDocument();
  });
});
