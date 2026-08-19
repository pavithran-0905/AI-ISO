import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useSession } from "@/auth/session";
import { ProjectMembersSection } from "@/features/settings/components/project-members-section";
import { useAddProjectMember, useProjectMembers, useRemoveProjectMember, useUpdateProjectMemberRole } from "@/features/settings/hooks/use-project-members";
import type { ProjectMember } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

vi.mock("@/auth/session", () => ({ useSession: vi.fn() }));
vi.mock("@/features/settings/hooks/use-project-members", () => ({
  useProjectMembers: vi.fn(),
  useAddProjectMember: vi.fn(),
  useUpdateProjectMemberRole: vi.fn(),
  useRemoveProjectMember: vi.fn(),
}));
vi.mock("@/state/toast-store", () => ({ toast: { success: vi.fn(), danger: vi.fn(), info: vi.fn() } }));

const SOLE_OWNER: ProjectMember = { id: "m1", projectId: "p1", userId: "owner-1", roleId: "r1", roleCode: "owner", roleName: "Owner", status: "active", invitedBy: null, createdAt: "2026-01-01T00:00:00Z" };
const OTHER_MEMBER: ProjectMember = { id: "m2", projectId: "p1", userId: "dev-1", roleId: "r2", roleCode: "developer", roleName: "Developer", status: "active", invitedBy: null, createdAt: "2026-01-01T00:00:00Z" };

function mockHooks(members: ProjectMember[]) {
  const removeMutateAsync = vi.fn();
  const updateRoleMutateAsync = vi.fn().mockResolvedValue(undefined);
  vi.mocked(useSession).mockReturnValue({ userId: "someone-else" } as unknown as ReturnType<typeof useSession>);
  vi.mocked(useProjectMembers).mockReturnValue({ data: members, isLoading: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof useProjectMembers>);
  vi.mocked(useAddProjectMember).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useAddProjectMember>);
  vi.mocked(useUpdateProjectMemberRole).mockReturnValue({ mutateAsync: updateRoleMutateAsync, isPending: false } as unknown as ReturnType<typeof useUpdateProjectMemberRole>);
  vi.mocked(useRemoveProjectMember).mockReturnValue({ mutateAsync: removeMutateAsync, isPending: false } as unknown as ReturnType<typeof useRemoveProjectMember>);
  return { removeMutateAsync, updateRoleMutateAsync };
}

describe("ProjectMembersSection", () => {
  it("renders nothing editable when the caller can't edit", () => {
    mockHooks([SOLE_OWNER]);
    render(<ProjectMembersSection projectId="p1" canEdit={false} />);
    expect(screen.queryByRole("button", { name: "Add member" })).not.toBeInTheDocument();
  });

  it("blocks removing the project's sole Owner, since the backend has no such guard", () => {
    const { removeMutateAsync } = mockHooks([SOLE_OWNER, OTHER_MEMBER]);
    render(<ProjectMembersSection projectId="p1" canEdit />);

    fireEvent.click(screen.getByRole("button", { name: `Remove ${SOLE_OWNER.userId}` }));

    expect(removeMutateAsync).not.toHaveBeenCalled();
    expect(toast.danger).toHaveBeenCalledWith("Can't remove this member", expect.stringContaining("only Owner"));
  });

  it("allows removing a non-owner member directly", async () => {
    const { removeMutateAsync } = mockHooks([SOLE_OWNER, OTHER_MEMBER]);
    render(<ProjectMembersSection projectId="p1" canEdit />);

    fireEvent.click(screen.getByRole("button", { name: `Remove ${OTHER_MEMBER.userId}` }));
    fireEvent.click(screen.getByRole("button", { name: "Remove member" }));

    await vi.waitFor(() => expect(removeMutateAsync).toHaveBeenCalledWith(OTHER_MEMBER.userId));
  });

  it("treats setting a role to owner as a distinct ownership transfer, requiring its own confirmation", async () => {
    const { updateRoleMutateAsync } = mockHooks([SOLE_OWNER, OTHER_MEMBER]);
    render(<ProjectMembersSection projectId="p1" canEdit />);

    fireEvent.change(screen.getByLabelText(`Role for ${OTHER_MEMBER.userId}`), { target: { value: "owner" } });
    expect(updateRoleMutateAsync).not.toHaveBeenCalled();
    expect(screen.getByText("Transfer project ownership?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Transfer ownership" }));
    await vi.waitFor(() => expect(updateRoleMutateAsync).toHaveBeenCalledWith({ userId: OTHER_MEMBER.userId, input: { roleCode: "owner" } }));
  });

  it("blocks demoting the project's sole Owner to a lesser role", () => {
    const { updateRoleMutateAsync } = mockHooks([SOLE_OWNER, OTHER_MEMBER]);
    render(<ProjectMembersSection projectId="p1" canEdit />);

    fireEvent.change(screen.getByLabelText(`Role for ${SOLE_OWNER.userId}`), { target: { value: "developer" } });

    expect(updateRoleMutateAsync).not.toHaveBeenCalled();
    expect(toast.danger).toHaveBeenCalledWith("Can't change this role", expect.stringContaining("only Owner"));
  });
});
