import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecentActivityTimeline } from "@/features/operations/components/recent-activity-timeline";
import { useAuditEvents } from "@/features/audit/hooks/use-audit";

vi.mock("@/features/audit/hooks/use-audit", () => ({ useAuditEvents: vi.fn() }));

describe("RecentActivityTimeline", () => {
  it("shows real compliance audit events and a link to full activity", () => {
    vi.mocked(useAuditEvents).mockReturnValue({
      data: {
        items: [
          {
            id: "e1",
            source: "compliance",
            action: "finding_raised",
            entityType: "finding",
            entityId: "f1",
            entityReference: "Unencrypted volume detected",
            actorId: "u1",
            actorType: "user",
            occurredAt: "2026-08-01T10:00:00Z",
            summary: "A finding was raised.",
            succeeded: true,
            changes: {},
            context: null,
          },
        ],
        offset: 0,
        limit: 8,
        hasMore: false,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAuditEvents>);

    render(<RecentActivityTimeline organizationId="org-1" />);
    expect(screen.getByText("Finding Raised")).toBeInTheDocument();
    expect(screen.getByText("Unencrypted volume detected")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View full activity" })).toHaveAttribute("href", "/audit/activity");
  });

  it("shows an empty state when nothing happened recently", () => {
    vi.mocked(useAuditEvents).mockReturnValue({
      data: { items: [], offset: 0, limit: 8, hasMore: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAuditEvents>);

    render(<RecentActivityTimeline organizationId="org-1" />);
    expect(screen.getByText("No recent activity")).toBeInTheDocument();
  });

  it("shows a retry-capable error state, independent of the rest of the workspace", () => {
    vi.mocked(useAuditEvents).mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() } as unknown as ReturnType<typeof useAuditEvents>);
    render(<RecentActivityTimeline organizationId="org-1" />);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
