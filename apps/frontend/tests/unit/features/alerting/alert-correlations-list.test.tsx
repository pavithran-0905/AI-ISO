import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertCorrelationsList } from "@/features/alerting/components/alert-correlations-list";
import { useAlertCorrelations } from "@/features/alerting/hooks/use-alert-correlations";

vi.mock("@/features/alerting/hooks/use-alert-correlations", () => ({ useAlertCorrelations: vi.fn() }));

const mocked = vi.mocked(useAlertCorrelations);

describe("AlertCorrelationsList", () => {
  it("links each correlated child alert to its own detail page", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { id: "c1", parentAlertId: "a1", childAlertId: "a2", correlationType: "duplicate", correlatedAt: "2026-01-01T00:00:00Z" },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertCorrelations>);

    render(<AlertCorrelationsList alertId="a1" />);

    expect(screen.getByText("duplicate")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /duplicate/ })).toHaveAttribute("href", "/alerting/alerts/a2");
  });

  it("shows an honest empty state when nothing is correlated", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertCorrelations>);

    render(<AlertCorrelationsList alertId="a1" />);

    expect(screen.getByText("No correlated alerts")).toBeInTheDocument();
  });
});
