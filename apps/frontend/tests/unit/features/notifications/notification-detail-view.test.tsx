import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NotificationDetailView } from "@/features/notifications/components/notification-detail-view";
import { useAcknowledgeNotification, useMarkNotificationRead } from "@/features/notifications/hooks/use-notifications";
import { useNotificationDeliveries } from "@/features/notifications/hooks/use-notifications";
import type { Notification } from "@/features/notifications/types";

vi.mock("@/features/notifications/hooks/use-notifications", () => ({
  useMarkNotificationRead: vi.fn(),
  useAcknowledgeNotification: vi.fn(),
  useNotificationDeliveries: vi.fn(),
}));

const NOTIFICATION: Notification = {
  id: "n1",
  organizationId: "org-1",
  userId: "user-1",
  category: "alert",
  priority: "high",
  status: "sent",
  subject: "Disk usage above threshold",
  body: "Disk usage on edge-01 exceeded 90%.",
  templateId: null,
  sourceService: "monitoring-service",
  sourceEventType: "disk.threshold_exceeded",
  correlationId: null,
  expiresAt: null,
  readAt: null,
  acknowledgedAt: null,
  tags: ["infrastructure"],
  metadata: { api_key: "sk-live-abc123", disk_percent: 92 },
  createdAt: "2026-08-01T10:00:00Z",
  updatedAt: "2026-08-01T10:00:00Z",
};

function mockHooks(overrides: { markRead?: ReturnType<typeof vi.fn>; acknowledge?: ReturnType<typeof vi.fn> } = {}) {
  vi.mocked(useMarkNotificationRead).mockReturnValue({
    mutate: overrides.markRead ?? vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof useMarkNotificationRead>);
  vi.mocked(useAcknowledgeNotification).mockReturnValue({
    mutate: overrides.acknowledge ?? vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof useAcknowledgeNotification>);
  vi.mocked(useNotificationDeliveries).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useNotificationDeliveries>);
}

describe("NotificationDetailView", () => {
  it("renders category, priority, status, source, and message from the real notification", () => {
    mockHooks();
    render(<NotificationDetailView organizationId="org-1" notification={NOTIFICATION} />);

    expect(screen.getByText("Alert")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
    expect(screen.getByText("monitoring-service")).toBeInTheDocument();
    expect(screen.getByText("Disk usage on edge-01 exceeded 90%.")).toBeInTheDocument();
  });

  it("masks a sensitive metadata key, never rendering the raw secret", () => {
    mockHooks();
    render(<NotificationDetailView organizationId="org-1" notification={NOTIFICATION} />);
    expect(screen.queryByText(/sk-live-abc123/)).not.toBeInTheDocument();
    expect(screen.getByText(/••••••••/)).toBeInTheDocument();
    expect(screen.getByText(/"disk_percent": 92/)).toBeInTheDocument();
  });

  it("shows Mark read for an unread notification, and calls the real mutation", () => {
    const markRead = vi.fn();
    mockHooks({ markRead });
    render(<NotificationDetailView organizationId="org-1" notification={NOTIFICATION} />);

    fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
    expect(markRead).toHaveBeenCalledWith({ organizationId: "org-1", notificationId: "n1" });
  });

  it("hides Mark read once already read", () => {
    mockHooks();
    render(<NotificationDetailView organizationId="org-1" notification={{ ...NOTIFICATION, readAt: "2026-08-01T10:05:00Z" }} />);
    expect(screen.queryByRole("button", { name: "Mark read" })).not.toBeInTheDocument();
  });

  it("hides Acknowledge once already acknowledged", () => {
    mockHooks();
    render(<NotificationDetailView organizationId="org-1" notification={{ ...NOTIFICATION, status: "acknowledged", acknowledgedAt: "2026-08-01T10:05:00Z" }} />);
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  });
});
