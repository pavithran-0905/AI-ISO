import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertFilters, EMPTY_ALERT_FILTERS } from "@/features/alerting/components/alert-filters";

describe("AlertFilters", () => {
  it("reports search input changes", () => {
    const onChange = vi.fn();
    render(<AlertFilters values={EMPTY_ALERT_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "database" } });

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_ALERT_FILTERS, query: "database" });
  });

  it("reports status and severity select changes", () => {
    const onChange = vi.fn();
    render(<AlertFilters values={EMPTY_ALERT_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "open" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_ALERT_FILTERS, status: "open" });

    fireEvent.change(screen.getByLabelText("Severity"), { target: { value: "critical" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_ALERT_FILTERS, severity: "critical" });
  });

  it("hides the reset control until a filter is active, then shows the active count", () => {
    const { rerender } = render(<AlertFilters values={EMPTY_ALERT_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /reset/i })).not.toBeInTheDocument();

    rerender(<AlertFilters values={{ query: "db", status: "open", severity: "" }} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("calls onReset when the reset button is clicked", () => {
    const onReset = vi.fn();
    render(<AlertFilters values={{ query: "db", status: "", severity: "" }} onChange={vi.fn()} onReset={onReset} />);

    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
