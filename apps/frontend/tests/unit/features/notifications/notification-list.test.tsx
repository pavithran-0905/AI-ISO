import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NotificationList } from "@/features/notifications/components/notification-list";
import type { Notification, NotificationSearchResult } from "@/features/notifications/types";

const NOTIFICATION: Notification = {
  id: "n1",
  organizationId: "org-1",
  userId: "user-1",
  category: "alert",
  priority: "critical",
  status: "sent",
  subject: "Disk usage above threshold",
  body: "Disk usage on edge-01 exceeded 90%.",
  templateId: null,
  sourceService: "monitoring-service",
  sourceEventType: null,
  correlationId: null,
  expiresAt: null,
  readAt: null,
  acknowledgedAt: null,
  tags: [],
  metadata: {},
  createdAt: "2026-08-01T10:00:00Z",
  updatedAt: "2026-08-01T10:00:00Z",
};

function result(overrides: Partial<NotificationSearchResult> = {}): NotificationSearchResult {
  return { items: [NOTIFICATION], offset: 0, limit: 25, hasMore: false, ...overrides };
}

describe("NotificationList", () => {
  it("renders subject, category, priority, and status for each real notification", () => {
    render(<NotificationList result={result()} items={[NOTIFICATION]} onPageChange={vi.fn()} />);
    expect(screen.getAllByText("Disk usage above threshold").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Alert").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Critical").length).toBeGreaterThan(0);
  });

  it("links each row to its real detail route", () => {
    render(<NotificationList result={result()} items={[NOTIFICATION]} onPageChange={vi.fn()} />);
    expect(screen.getAllByRole("link", { name: "Disk usage above threshold" })[0]).toHaveAttribute("href", "/notifications/n1");
  });

  it("disables Next once hasMore is false, and pages by the real limit", () => {
    const onPageChange = vi.fn();
    render(<NotificationList result={result({ offset: 25, limit: 25, hasMore: true })} items={[NOTIFICATION]} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenCalledWith(50);
  });

  it("labels a client-side-filtered quick view distinctly from the full loaded page", () => {
    const twoItemResult = result({ items: [NOTIFICATION, { ...NOTIFICATION, id: "n2" }] });
    render(<NotificationList result={twoItemResult} items={[NOTIFICATION]} onPageChange={vi.fn()} />);
    expect(screen.getByText(/1 of 2 loaded shown/)).toBeInTheDocument();
  });
});
