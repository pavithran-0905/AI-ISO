import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventDetailDrawer } from "@/features/audit/components/event-detail-drawer";
import type { AuditEvent } from "@/features/audit/types";

const EVENT: AuditEvent = {
  id: "evt-1",
  source: "compliance",
  action: "control_updated",
  entityType: "control",
  entityId: "c-1",
  entityReference: "Access Control Policy",
  actorId: "auditor-42",
  actorType: "user",
  occurredAt: "2026-08-01T10:00:00Z",
  summary: "Control was updated by an administrator.",
  succeeded: true,
  changes: { field: "status", previous_value: "draft", new_value: "active", api_key: "sk-live-abc123" },
  context: null,
};

describe("EventDetailDrawer", () => {
  it("shows nothing while no event is selected", () => {
    render(<EventDetailDrawer event={null} onClose={vi.fn()} />);
    expect(screen.queryByText("Actor")).not.toBeInTheDocument();
  });

  it("renders actor, action, resource, status, and timestamp from the real selected event — no second fetch", () => {
    render(<EventDetailDrawer event={EVENT} onClose={vi.fn()} />);
    expect(screen.getByText("auditor-42")).toBeInTheDocument();
    expect(screen.getAllByText("Control Updated").length).toBeGreaterThan(0);
    expect(screen.getByText("Access Control Policy")).toBeInTheDocument();
    expect(screen.getByText("Success")).toBeInTheDocument();
  });

  it("masks a sensitive key inside changes/context, never rendering the raw secret value", () => {
    render(<EventDetailDrawer event={EVENT} onClose={vi.fn()} />);
    expect(screen.queryByText(/sk-live-abc123/)).not.toBeInTheDocument();
    expect(screen.getByText(/••••••••/)).toBeInTheDocument();
  });

  it("still shows non-sensitive change fields unmasked", () => {
    render(<EventDetailDrawer event={EVENT} onClose={vi.fn()} />);
    expect(screen.getByText(/"previous_value": "draft"/)).toBeInTheDocument();
    expect(screen.getByText(/"new_value": "active"/)).toBeInTheDocument();
  });

  it("omits a Context block when the source doesn't return one (compliance-service's response has none)", () => {
    render(<EventDetailDrawer event={EVENT} onClose={vi.fn()} />);
    expect(screen.queryByText("Context")).not.toBeInTheDocument();
  });
});
