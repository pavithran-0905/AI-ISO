import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PreferencesForm } from "@/features/settings/components/preferences-form";
import { useUpdateUserPreferences } from "@/features/settings/hooks/use-preferences";
import type { UserPreferences } from "@/features/settings/types";
import { useOrganizations } from "@/organization/use-organizations";

vi.mock("@/features/settings/hooks/use-preferences", () => ({ useUpdateUserPreferences: vi.fn() }));
vi.mock("@/organization/use-organizations", () => ({ useOrganizations: vi.fn() }));

const PREFERENCES: UserPreferences = {
  userId: "u1",
  language: "en",
  theme: "dark",
  timezone: "UTC",
  dateFormat: "YYYY-MM-DD",
  timeFormat: "24h",
  dashboardPreferences: { widgets: ["a"] },
  notificationPreferences: { muted: true },
  accessibility: { highContrast: true },
  defaultOrganizationId: null,
  defaultProjectId: null,
};

describe("PreferencesForm", () => {
  it("resends theme and every opaque blob unchanged, since PUT resets anything omitted", async () => {
    vi.mocked(useOrganizations).mockReturnValue({ data: [] } as unknown as ReturnType<typeof useOrganizations>);
    const mutateAsync = vi.fn().mockResolvedValue(PREFERENCES);
    vi.mocked(useUpdateUserPreferences).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof useUpdateUserPreferences>);

    render(<PreferencesForm preferences={PREFERENCES} />);
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "fr" } });
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        language: "fr",
        theme: "dark",
        dashboardPreferences: { widgets: ["a"] },
        notificationPreferences: { muted: true },
        accessibility: { highContrast: true },
      }),
    );
  });
});
