import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuditEventTable } from "@/features/audit/components/audit-event-table";
import type { AuditEvent, AuditEventSearchResult } from "@/features/audit/types";

const EVENT: AuditEvent = {
  id: "evt-1",
  source: "compliance",
  action: "finding_raised",
  entityType: "finding",
  entityId: "f-1",
  entityReference: "Unencrypted volume detected",
  actorId: "user-123",
  actorType: "user",
  occurredAt: "2026-08-01T10:00:00Z",
  summary: "A finding was raised.",
  succeeded: true,
  changes: {},
  context: null,
};

function result(overrides: Partial<AuditEventSearchResult> = {}): AuditEventSearchResult {
  return { items: [EVENT], offset: 0, limit: 25, hasMore: false, ...overrides };
}

describe("AuditEventTable", () => {
  // Both the desktop table and the mobile card list render in jsdom at
  // once (the split is CSS-only, `hidden md:block`/`md:hidden`), so
  // every row's content appears twice — `getAllByText` throughout,
  // never `getByText`.
  it("renders the action, resource, and status for each real event", () => {
    render(<AuditEventTable result={result()} onPageChange={vi.fn()} onSelectEvent={vi.fn()} />);
    expect(screen.getAllByText("Finding Raised").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unencrypted volume detected").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Success").length).toBeGreaterThan(0);
  });

  it("shows a Failure status for an unsucceeded event, never a fabricated 'Denied'", () => {
    render(<AuditEventTable result={result({ items: [{ ...EVENT, succeeded: false }] })} onPageChange={vi.fn()} onSelectEvent={vi.fn()} />);
    expect(screen.getAllByText("Failure").length).toBeGreaterThan(0);
    expect(screen.queryByText("Denied")).not.toBeInTheDocument();
  });

  it("disables Previous on the first page and Next once hasMore is false", () => {
    render(<AuditEventTable result={result()} onPageChange={vi.fn()} onSelectEvent={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("pages forward and backward by the real limit, since no total count exists to page against", () => {
    const onPageChange = vi.fn();
    render(<AuditEventTable result={result({ offset: 25, limit: 25, hasMore: true })} onPageChange={onPageChange} onSelectEvent={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenCalledWith(50);

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(onPageChange).toHaveBeenCalledWith(0);
  });

  it("opens the detail drawer target via onSelectEvent when a row's View action is used", () => {
    const onSelectEvent = vi.fn();
    render(<AuditEventTable result={result()} onPageChange={vi.fn()} onSelectEvent={onSelectEvent} />);

    fireEvent.click(screen.getAllByRole("button", { name: "View" })[0]);
    expect(onSelectEvent).toHaveBeenCalledWith(EVENT);
  });
});
