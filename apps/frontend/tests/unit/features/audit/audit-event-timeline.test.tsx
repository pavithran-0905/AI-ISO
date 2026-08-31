import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuditEventTimeline } from "@/features/audit/components/audit-event-timeline";
import type { AuditEvent, AuditEventSearchResult } from "@/features/audit/types";

const EVENTS: AuditEvent[] = [
  {
    id: "evt-1",
    source: "notifications",
    action: "template_updated",
    entityType: "template",
    entityId: "t-1",
    entityReference: "Incident escalation template",
    actorId: "user-1",
    actorType: "user",
    occurredAt: "2026-08-01T10:42:00Z",
    summary: "Template updated.",
    succeeded: true,
    changes: {},
    context: { channel: "email" },
  },
  {
    id: "evt-2",
    source: "notifications",
    action: "broadcast_initiated",
    entityType: "broadcast",
    entityId: "b-1",
    entityReference: "Maintenance notice",
    actorId: "user-2",
    actorType: "user",
    occurredAt: "2026-08-01T10:39:00Z",
    summary: "Broadcast initiated.",
    succeeded: false,
    changes: {},
    context: null,
  },
];

function result(): AuditEventSearchResult {
  return { items: EVENTS, offset: 0, limit: 25, hasMore: false };
}

describe("AuditEventTimeline", () => {
  it("renders as a real ordered list — the accessible structured equivalent §46 requires, not a purely visual timeline", () => {
    render(<AuditEventTimeline result={result()} />);
    const list = screen.getByRole("list");
    expect(list.tagName).toBe("OL");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("shows each event's real action, resource, and status, newest entries first as the backend returns them", () => {
    render(<AuditEventTimeline result={result()} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Template Updated");
    expect(items[0]).toHaveTextContent("Incident escalation template");
    expect(items[0]).toHaveTextContent("Success");
    expect(items[1]).toHaveTextContent("Broadcast Initiated");
    expect(items[1]).toHaveTextContent("Failure");
  });

  it("renders an empty list without error when there are no events", () => {
    render(<AuditEventTimeline result={{ items: [], offset: 0, limit: 25, hasMore: false }} />);
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});
