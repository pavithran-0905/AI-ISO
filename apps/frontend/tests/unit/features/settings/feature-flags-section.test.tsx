import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FeatureFlagsSection } from "@/features/settings/components/feature-flags-section";
import { useCreateFeatureFlag, useFeatureFlags, useUpdateFeatureFlag } from "@/features/settings/hooks/use-system-settings";

vi.mock("@/features/settings/hooks/use-system-settings", () => ({
  useFeatureFlags: vi.fn(),
  useCreateFeatureFlag: vi.fn(),
  useUpdateFeatureFlag: vi.fn(),
}));

const FLAG = { id: "f1", name: "new-topology-canvas", scope: "global", targetRef: null, rolloutPercentage: 50, isEnabled: true, isKilled: false };

describe("FeatureFlagsSection", () => {
  it("toggles isEnabled independently of the kill switch", async () => {
    vi.mocked(useFeatureFlags).mockReturnValue({ data: [FLAG], isLoading: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof useFeatureFlags>);
    vi.mocked(useCreateFeatureFlag).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useCreateFeatureFlag>);
    const updateFlag = vi.fn().mockResolvedValue(FLAG);
    vi.mocked(useUpdateFeatureFlag).mockReturnValue({ mutateAsync: updateFlag, isPending: false } as unknown as ReturnType<typeof useUpdateFeatureFlag>);

    render(<FeatureFlagsSection />);
    fireEvent.click(screen.getByRole("switch", { name: "new-topology-canvas enabled" }));

    await vi.waitFor(() => expect(updateFlag).toHaveBeenCalledWith({ flagId: "f1", input: { isEnabled: false } }));
  });

  it("kills a flag via the separate kill switch, not the enabled toggle", async () => {
    vi.mocked(useFeatureFlags).mockReturnValue({ data: [FLAG], isLoading: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof useFeatureFlags>);
    vi.mocked(useCreateFeatureFlag).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useCreateFeatureFlag>);
    const updateFlag = vi.fn().mockResolvedValue(FLAG);
    vi.mocked(useUpdateFeatureFlag).mockReturnValue({ mutateAsync: updateFlag, isPending: false } as unknown as ReturnType<typeof useUpdateFeatureFlag>);

    render(<FeatureFlagsSection />);
    fireEvent.click(screen.getByRole("button", { name: "Kill" }));

    await vi.waitFor(() => expect(updateFlag).toHaveBeenCalledWith({ flagId: "f1", input: { isKilled: true } }));
  });
});
