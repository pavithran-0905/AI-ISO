import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecommendationList } from "@/features/ai-assistant/components/recommendation-list";
import { useDecideRecommendation, useRecommendations } from "@/features/ai-assistant/hooks/use-insights";
import type { Recommendation } from "@/features/ai-assistant/types";
import { usePermissions } from "@/permissions/hooks";

vi.mock("@/features/ai-assistant/hooks/use-insights", () => ({ useRecommendations: vi.fn(), useDecideRecommendation: vi.fn() }));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

const mockedRecommendations = vi.mocked(useRecommendations);
const mockedDecide = vi.mocked(useDecideRecommendation);
const mockedPermissions = vi.mocked(usePermissions);

const PROPOSED: Recommendation = {
  id: "r1",
  organizationId: "org-1",
  conversationId: null,
  recommendationType: "automation",
  title: "Automate weekly certificate rotation",
  body: "Rotate TLS certificates on a schedule instead of manually.",
  rationale: "Several near-miss expirations this quarter.",
  citations: [],
  confidence: 0.8,
  status: "proposed",
  decidedBy: null,
};

function setup({ can }: { can: (action: string) => boolean }) {
  mockedRecommendations.mockReturnValue({ data: [PROPOSED], isLoading: false, isError: false } as unknown as ReturnType<typeof useRecommendations>);
  mockedDecide.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(PROPOSED), isPending: false } as unknown as ReturnType<typeof useDecideRecommendation>);
  mockedPermissions.mockReturnValue({ role: "operator", can, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);
}

describe("RecommendationList", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows Accept/Reject for a role the coarse capability model grants approve to", () => {
    setup({ can: () => true });
    render(<RecommendationList organizationId="org-1" />);

    expect(screen.getByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("hides Accept/Reject for a role the coarse capability model denies approve to", () => {
    setup({ can: () => false });
    render(<RecommendationList organizationId="org-1" />);

    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });

  it("calls decide with accept=true when Accept is pressed", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(PROPOSED);
    mockedRecommendations.mockReturnValue({ data: [PROPOSED], isLoading: false, isError: false } as unknown as ReturnType<typeof useRecommendations>);
    mockedDecide.mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof useDecideRecommendation>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    render(<RecommendationList organizationId="org-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ recommendationId: "r1", accept: true }));
  });

  it("does not show a decision action on an already-decided recommendation, regardless of role", () => {
    mockedRecommendations.mockReturnValue({
      data: [{ ...PROPOSED, status: "accepted", decidedBy: "u1" }],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useRecommendations>);
    mockedDecide.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDecideRecommendation>);
    mockedPermissions.mockReturnValue({ role: "operator", can: () => true, isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);

    render(<RecommendationList organizationId="org-1" />);

    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
  });
});
