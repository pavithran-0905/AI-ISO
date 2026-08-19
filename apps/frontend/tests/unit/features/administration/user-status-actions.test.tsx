import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useSession } from "@/auth/session";
import { UserStatusActions } from "@/features/administration/components/user-status-actions";
import { usePatchUser, useRemoveUser } from "@/features/administration/hooks/use-users";
import type { UserDetail } from "@/features/administration/types";

vi.mock("@/auth/session", () => ({ useSession: vi.fn() }));
vi.mock("@/features/administration/hooks/use-users", () => ({ usePatchUser: vi.fn(), useRemoveUser: vi.fn() }));

const USER: UserDetail = {
  id: "u1",
  username: "sarun",
  email: "sarun@example.com",
  displayName: "Sarun",
  firstName: null,
  middleName: null,
  lastName: null,
  phoneNumber: null,
  avatar: null,
  timezone: "UTC",
  language: "en",
  locale: "en-US",
  status: "active",
  lastLogin: null,
  metadata: {},
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("UserStatusActions", () => {
  it("warns when the viewed account is the caller's own, and highlights a self-restricting status change", () => {
    vi.mocked(useSession).mockReturnValue({ userId: "u1" } as unknown as ReturnType<typeof useSession>);
    vi.mocked(usePatchUser).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof usePatchUser>);
    vi.mocked(useRemoveUser).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useRemoveUser>);

    render(<UserStatusActions user={USER} />);
    expect(screen.getByText(/You are viewing your own account/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Change status"), { target: { value: "suspended" } });
    expect(screen.getByText(/would restrict your own access/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change anyway" })).toBeInTheDocument();
  });

  it("does not warn about self-restriction when viewing someone else's account", () => {
    vi.mocked(useSession).mockReturnValue({ userId: "someone-else" } as unknown as ReturnType<typeof useSession>);
    vi.mocked(usePatchUser).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof usePatchUser>);
    vi.mocked(useRemoveUser).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useRemoveUser>);

    render(<UserStatusActions user={USER} />);
    fireEvent.change(screen.getByLabelText("Change status"), { target: { value: "suspended" } });

    expect(screen.queryByText(/would restrict your own access/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
  });

  it("submits the chosen status via PATCH, and shows the backend's real error on an illegal transition", async () => {
    vi.mocked(useSession).mockReturnValue({ userId: "someone-else" } as unknown as ReturnType<typeof useSession>);
    const mutateAsync = vi.fn().mockResolvedValue(USER);
    vi.mocked(usePatchUser).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof usePatchUser>);
    vi.mocked(useRemoveUser).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useRemoveUser>);

    render(<UserStatusActions user={USER} />);
    fireEvent.change(screen.getByLabelText("Change status"), { target: { value: "inactive" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ status: "inactive" }));
  });

  it("requires confirmation before removing a user", () => {
    vi.mocked(useSession).mockReturnValue({ userId: "someone-else" } as unknown as ReturnType<typeof useSession>);
    vi.mocked(usePatchUser).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof usePatchUser>);
    const removeMutateAsync = vi.fn();
    vi.mocked(useRemoveUser).mockReturnValue({ mutateAsync: removeMutateAsync, isPending: false } as unknown as ReturnType<typeof useRemoveUser>);

    render(<UserStatusActions user={USER} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove user" }));

    expect(removeMutateAsync).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
