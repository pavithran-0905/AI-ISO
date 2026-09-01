import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSession } from "@/auth/session";
import { NotificationSummaryWidget } from "@/features/dashboard/components/notification-summary-widget";
import { useRecentNotifications } from "@/features/notifications/hooks/use-notifications";
import type { Notification } from "@/features/notifications/types";

vi.mock("@/auth/session", () => ({ useSession: vi.fn() }));
vi.mock("@/features/notifications/hooks/use-notifications", () => ({ useRecentNotifications: vi.fn() }));

const mockedSession = vi.mocked(useSession);
const mockedNotifications = vi.mocked(useRecentNotifications);

function notification(overrides: Partial<Notification>): Notification {
  return {
    id: "n1",
    organizationId: "org-1",
    userId: "user-1",
    category: "information",
    priority: "normal",
    status: "delivered",
    subject: "Something happened",
    body: "Details",
    templateId: null,
    sourceService: "monitoring",
    sourceEventType: null,
    correlationId: null,
    expiresAt: null,
    readAt: "2026-01-01T00:00:00Z",
    acknowledgedAt: null,
    tags: [],
    metadata: {},
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("NotificationSummaryWidget", () => {
  beforeEach(() => {
    mockedSession.mockReturnValue({ userId: "user-1" } as unknown as ReturnType<typeof useSession>);
  });

  it("shows an honest empty state with zero notifications", () => {
    mockedNotifications.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [], offset: 0, limit: 8, hasMore: false },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationSummaryWidget organizationId="org-1" />);
    expect(screen.getByText("No recent notifications")).toBeInTheDocument();
  });

  it("prioritizes important (critical/high) notifications when any exist", () => {
    mockedNotifications.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          notification({ id: "normal", subject: "Normal item", priority: "normal" }),
          notification({ id: "urgent", subject: "Urgent item", priority: "critical" }),
        ],
        offset: 0,
        limit: 8,
        hasMore: false,
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationSummaryWidget organizationId="org-1" />);
    expect(screen.getByText("Urgent item")).toBeInTheDocument();
    expect(screen.queryByText("Normal item")).not.toBeInTheDocument();
  });

  it("never shows a total-unread count — only an Unread badge on an individual unread item", () => {
    mockedNotifications.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [notification({ id: "n1", subject: "Unseen item", readAt: null })], offset: 0, limit: 8, hasMore: false },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationSummaryWidget organizationId="org-1" />);
    expect(screen.getByText("Unread")).toBeInTheDocument();
    expect(screen.queryByText(/\d+ unread/i)).not.toBeInTheDocument();
  });

  it("links to the real notification detail page", () => {
    mockedNotifications.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [notification({ id: "n1", subject: "Item" })], offset: 0, limit: 8, hasMore: false },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecentNotifications>);

    render(<NotificationSummaryWidget organizationId="org-1" />);
    expect(screen.getByRole("link", { name: "View notifications" })).toHaveAttribute("href", "/notifications");
  });
});
