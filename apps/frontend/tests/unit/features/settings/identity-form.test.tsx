import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useSession } from "@/auth/session";
import { IdentityForm } from "@/features/settings/components/identity-form";
import { usePatchUserIdentity } from "@/features/settings/hooks/use-preferences";

vi.mock("@/auth/session", () => ({ useSession: vi.fn() }));
vi.mock("@/features/settings/hooks/use-preferences", () => ({ usePatchUserIdentity: vi.fn() }));

describe("IdentityForm", () => {
  it("patches using the caller's own id from the session, never anything else", async () => {
    vi.mocked(useSession).mockReturnValue({
      userId: "u1",
      user: { displayName: "Sarun", email: "sarun@example.com", id: "u1", isEmailVerified: true, mfaEnabled: false, lastLoginAt: null, createdAt: "2026-01-01T00:00:00Z" },
    } as unknown as ReturnType<typeof useSession>);
    const mutateAsync = vi.fn().mockResolvedValue(undefined);
    vi.mocked(usePatchUserIdentity).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof usePatchUserIdentity>);

    render(<IdentityForm />);
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New Name" } });
    fireEvent.click(screen.getByRole("button", { name: "Save identity" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync).toHaveBeenCalledWith({
      userId: "u1",
      input: { displayName: "New Name", firstName: undefined, lastName: undefined, phoneNumber: undefined },
    });
  });

  it("does not submit when there is no session user id", () => {
    vi.mocked(useSession).mockReturnValue({ userId: null, user: null } as unknown as ReturnType<typeof useSession>);
    const mutateAsync = vi.fn();
    vi.mocked(usePatchUserIdentity).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof usePatchUserIdentity>);

    render(<IdentityForm />);
    fireEvent.click(screen.getByRole("button", { name: "Save identity" }));

    expect(mutateAsync).not.toHaveBeenCalled();
  });
});
