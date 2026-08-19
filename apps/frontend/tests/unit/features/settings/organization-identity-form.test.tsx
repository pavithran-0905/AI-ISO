import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OrganizationIdentityForm } from "@/features/settings/components/organization-identity-form";
import { useUpdateOrganizationIdentity } from "@/features/settings/hooks/use-organization-settings";
import type { OrganizationIdentity } from "@/features/settings/types";

vi.mock("@/features/settings/hooks/use-organization-settings", () => ({ useUpdateOrganizationIdentity: vi.fn() }));

const IDENTITY: OrganizationIdentity = {
  id: "org-1",
  slug: "acme",
  name: "Acme",
  displayName: "Acme Corp",
  shortName: null,
  description: null,
  status: "active",
  primaryDomain: "acme.com",
  primaryContactEmail: "ops@acme.com",
  logoUrl: null,
  website: null,
  industry: null,
  timezone: "UTC",
  language: "en",
  country: null,
  currency: "USD",
  metadata: { tier: "enterprise" },
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-02T00:00:00Z",
};

describe("OrganizationIdentityForm", () => {
  it("shows read-only values and no editable controls when the caller can't edit", () => {
    vi.mocked(useUpdateOrganizationIdentity).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useUpdateOrganizationIdentity>);
    render(<OrganizationIdentityForm identity={IDENTITY} canEdit={false} />);

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save identity" })).not.toBeInTheDocument();
  });

  it("resends the full object, including unchanged metadata, since PUT resets omitted fields", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(IDENTITY);
    vi.mocked(useUpdateOrganizationIdentity).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof useUpdateOrganizationIdentity>);

    render(<OrganizationIdentityForm identity={IDENTITY} canEdit />);
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Acme Corp Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save identity" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ displayName: "Acme Corp Renamed", metadata: { tier: "enterprise" }, currency: "USD" }),
    );
  });
});
