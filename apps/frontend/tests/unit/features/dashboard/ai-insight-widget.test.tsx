import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AiInsightWidget } from "@/features/dashboard/components/ai-insight-widget";
import { useRecommendations } from "@/features/ai-assistant/hooks/use-insights";

vi.mock("@/features/ai-assistant/hooks/use-insights", () => ({ useRecommendations: vi.fn() }));

const mocked = vi.mocked(useRecommendations);

describe("AiInsightWidget", () => {
  it("always renders the Ask AI action, regardless of the recommendations fetch", () => {
    mocked.mockReturnValue({ isLoading: false, isError: true, data: undefined, error: new Error("boom"), refetch: vi.fn() } as unknown as ReturnType<
      typeof useRecommendations
    >);

    render(<AiInsightWidget organizationId="org-1" />);
    expect(screen.getByRole("link", { name: /ask ai/i })).toHaveAttribute("href", expect.stringContaining("/intelligence/assistant"));
  });

  it("shows a real pending-recommendation count when the fetch succeeds", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { id: "r1", status: "proposed" },
        { id: "r2", status: "accepted" },
        { id: "r3", status: "proposed" },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecommendations>);

    render(<AiInsightWidget organizationId="org-1" />);
    expect(screen.getByText("2 recommendations awaiting review.")).toBeInTheDocument();
  });

  it("never renders inline AI-generated analysis text — only the real count and the Ask AI redirect", () => {
    mocked.mockReturnValue({ isLoading: false, isError: false, data: [], error: null, refetch: vi.fn() } as unknown as ReturnType<
      typeof useRecommendations
    >);

    render(<AiInsightWidget organizationId="org-1" />);
    expect(screen.getByText("No recommendations awaiting review.")).toBeInTheDocument();
  });
});
