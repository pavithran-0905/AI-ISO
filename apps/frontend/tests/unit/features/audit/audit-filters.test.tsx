import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuditFilters, EMPTY_AUDIT_FILTERS } from "@/features/audit/components/audit-filters";

describe("AuditFilters", () => {
  it("shows compliance's real filter set: entity type/ID, actor ID, and a date-range preset — no action filter, since that route has none", () => {
    render(<AuditFilters source="compliance" values={EMPTY_AUDIT_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByLabelText("Entity type")).toBeInTheDocument();
    expect(screen.getByLabelText("Entity ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Actor ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Date range")).toBeInTheDocument();
    expect(screen.queryByLabelText("Action")).not.toBeInTheDocument();
  });

  it("shows only a plain note for integrations, since that route has no filter beyond organization scope", () => {
    render(<AuditFilters source="integrations" values={EMPTY_AUDIT_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText(/no additional filters/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Entity ID")).not.toBeInTheDocument();
  });

  it("shows notifications' real action dropdown populated only with its own confirmed AuditAction values", () => {
    render(<AuditFilters source="notifications" values={EMPTY_AUDIT_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    const actionSelect = screen.getByLabelText("Action");
    expect(actionSelect).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Broadcast Initiated" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Framework Created" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Entity ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Actor ID")).toBeInTheDocument();
    expect(screen.queryByLabelText("Entity type")).not.toBeInTheDocument();
  });

  it("commits a debounced text field after typing settles, without committing on every keystroke", async () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<AuditFilters source="compliance" values={EMPTY_AUDIT_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Actor ID"), { target: { value: "user-1" } });
    expect(onChange).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_AUDIT_FILTERS, actorId: "user-1" });
    vi.useRealTimers();
  });

  it("only shows the Reset control once a filter is active, and calls onReset when clicked", () => {
    const onReset = vi.fn();
    const { rerender } = render(<AuditFilters source="compliance" values={EMPTY_AUDIT_FILTERS} onChange={vi.fn()} onReset={onReset} />);
    expect(screen.queryByRole("button", { name: /Reset/ })).not.toBeInTheDocument();

    rerender(<AuditFilters source="compliance" values={{ ...EMPTY_AUDIT_FILTERS, actorId: "user-1" }} onChange={vi.fn()} onReset={onReset} />);
    fireEvent.click(screen.getByRole("button", { name: /Reset/ }));
    expect(onReset).toHaveBeenCalled();
  });
});
