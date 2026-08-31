import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EMPTY_NOTIFICATION_FILTERS, NotificationFilters } from "@/features/notifications/components/notification-filters";

describe("NotificationFilters", () => {
  it("shows the real category and status filters, populated only from confirmed backend enums", () => {
    render(<NotificationFilters values={EMPTY_NOTIFICATION_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);

    expect(screen.getByLabelText("Category")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Approval Request" })).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Acknowledged" })).toBeInTheDocument();
  });

  it("only shows Reset once a filter is active", () => {
    const { rerender } = render(<NotificationFilters values={EMPTY_NOTIFICATION_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /Reset/ })).not.toBeInTheDocument();

    rerender(<NotificationFilters values={{ category: "alert", status: "" }} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Reset/ })).toBeInTheDocument();
  });

  it("calls onChange immediately on selection, and onReset when Reset is clicked", () => {
    const onChange = vi.fn();
    const onReset = vi.fn();
    render(<NotificationFilters values={{ category: "alert", status: "" }} onChange={onChange} onReset={onReset} />);

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "read" } });
    expect(onChange).toHaveBeenCalledWith({ category: "alert", status: "read" });

    fireEvent.click(screen.getByRole("button", { name: /Reset/ }));
    expect(onReset).toHaveBeenCalled();
  });
});
