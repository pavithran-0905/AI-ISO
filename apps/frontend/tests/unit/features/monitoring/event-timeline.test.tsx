import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventTimeline } from "@/features/monitoring/components/event-timeline";
import { useObservabilityEvents } from "@/features/monitoring/hooks/use-observability-events";

vi.mock("@/features/monitoring/hooks/use-observability-events", () => ({
  useObservabilityEvents: vi.fn(),
}));

const mocked = vi.mocked(useObservabilityEvents);

function event(overrides: Record<string, unknown>) {
  return {
    id: "e1",
    eventKind: "platform",
    severity: "info",
    title: "Something happened",
    occurredAt: "2026-01-01T00:00:00Z",
    endedAt: null,
    serviceName: "gateway",
    ...overrides,
  };
}

describe("EventTimeline", () => {
  it("orders events newest-first by their real occurred_at timestamp", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        event({ id: "old", title: "Old event", occurredAt: "2026-01-01T00:00:00Z" }),
        event({ id: "new", title: "New event", occurredAt: "2026-01-02T00:00:00Z" }),
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useObservabilityEvents>);

    render(<EventTimeline />);

    const titles = screen.getAllByText(/event$/i).map((el) => el.textContent);
    expect(titles[0]).toBe("New event");
    expect(titles[1]).toBe("Old event");
  });

  it("caps the list when a limit is given", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [event({ id: "1", title: "First" }), event({ id: "2", title: "Second" })],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useObservabilityEvents>);

    render(<EventTimeline limit={1} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });

  it("shows an honest empty state when there are no events", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useObservabilityEvents>);

    render(<EventTimeline />);

    expect(screen.getByText("No recent events")).toBeInTheDocument();
  });
});
