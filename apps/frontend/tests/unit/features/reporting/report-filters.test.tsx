import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EMPTY_REPORT_FILTERS, ReportFilters } from "@/features/reporting/components/report-filters";

describe("ReportFilters", () => {
  it("reports search input changes", () => {
    const onChange = vi.fn();
    render(<ReportFilters values={EMPTY_REPORT_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "weekly" } });

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_REPORT_FILTERS, query: "weekly" });
  });

  it("reports category and enabled-only changes", () => {
    const onChange = vi.fn();
    render(<ReportFilters values={EMPTY_REPORT_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "compliance" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_REPORT_FILTERS, category: "compliance" });

    fireEvent.click(screen.getByLabelText("Enabled only"));
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_REPORT_FILTERS, enabledOnly: true });
  });

  it("hides the reset control until a filter is active, then shows the active count", () => {
    const { rerender } = render(<ReportFilters values={EMPTY_REPORT_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /reset/i })).not.toBeInTheDocument();

    rerender(<ReportFilters values={{ query: "x", category: "compliance", enabledOnly: true }} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("calls onReset when the reset button is clicked", () => {
    const onReset = vi.fn();
    render(<ReportFilters values={{ query: "x", category: "", enabledOnly: false }} onChange={vi.fn()} onReset={onReset} />);

    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
