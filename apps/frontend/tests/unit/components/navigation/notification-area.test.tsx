import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useSession } from "@/auth/session";
import { NotificationArea } from "@/components/navigation/notification-area";
import { useRecentNotifications } from "@/features/notifications/hooks/use-notifications";
import { useSelectedOrganization } from "@/organization/use-organizations";
import type { Notification } from "@/features/notifications/types";

vi.mock("@/auth/session", () => ({ useSession: vi.fn() }));
vi.mock("@/organization/use-organizations", () => ({ useSelectedOrganization: vi.fn() }));
vi.mock("@/features/notifications/hooks/use-notifications", () => ({ useRecentNotifications: vi.fn() }));

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

function mockCommon() {
  vi.mocked(useSession).mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
  vi.mocked(useSelectedOrganization).mockReturnValue({
    organizations: undefined,
    isLoading: false,
    isError: false,
    error: null,
    selectedOrganizationId: "org-1",
    needsSelection: false,
    hasNoAccess: false,
  });
}

describe("NotificationArea", () => {
  it("shows no unread dot and keeps the panel closed until the bell is clicked, when there are no notifications", () => {
    mockCommon();
    vi.mocked(useRecentNotifications).mockReturnValue({
      data: { items: [], offset: 0, limit: 8, hasMore: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationArea />);

    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.queryByText("You're all caught up")).not.toBeInTheDocument();
  });

  it("opens the panel on click and shows the honest empty state when the real page has no items", () => {
    mockCommon();
    vi.mocked(useRecentNotifications).mockReturnValue({
      data: { items: [], offset: 0, limit: 8, hasMore: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationArea />);
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
  });

  it("shows an unread dot and lists real notifications, never a fabricated count", () => {
    mockCommon();
    vi.mocked(useRecentNotifications).mockReturnValue({
      data: { items: [NOTIFICATION], offset: 0, limit: 8, hasMore: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationArea />);
    expect(screen.getByRole("button", { name: "Notifications, unread items" })).toBeInTheDocument();
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Notifications, unread items" }));
    expect(screen.getByText("Disk usage above threshold")).toBeInTheDocument();
  });

  it("shows a plain error message on failure, never blocking the rest of the shell", () => {
    mockCommon();
    vi.mocked(useRecentNotifications).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationArea />);
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByText("Unable to load notifications right now.")).toBeInTheDocument();
  });
});
