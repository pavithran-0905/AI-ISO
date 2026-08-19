import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RoleAssignmentSection } from "@/features/administration/components/role-assignment-section";
import { useAssignRole, useRbacRoles } from "@/features/administration/hooks/use-rbac";

vi.mock("@/features/administration/hooks/use-rbac", () => ({ useRbacRoles: vi.fn(), useAssignRole: vi.fn() }));

describe("RoleAssignmentSection", () => {
  it("always shows the no-live-effect warning, not just in a tooltip or docs", () => {
    vi.mocked(useRbacRoles).mockReturnValue({ data: [] } as unknown as ReturnType<typeof useRbacRoles>);
    vi.mocked(useAssignRole).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useAssignRole>);

    render(<RoleAssignmentSection userId="u1" />);
    expect(screen.getByText("This does not grant real access")).toBeInTheDocument();
  });

  it("submits the selected role id and scope to the real assignment endpoint", async () => {
    vi.mocked(useRbacRoles).mockReturnValue({
      data: [{ id: "role-1", name: "Viewer", code: "viewer", description: null, roleType: "system", status: "active", isSystem: true, priority: 10, organizationId: null, projectId: null }],
    } as unknown as ReturnType<typeof useRbacRoles>);
    const mutateAsync = vi.fn().mockResolvedValue({});
    vi.mocked(useAssignRole).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof useAssignRole>);

    render(<RoleAssignmentSection userId="u1" />);
    fireEvent.click(screen.getByRole("button", { name: "Assign a role" }));
    fireEvent.change(screen.getByLabelText("Role*"), { target: { value: "role-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Record assignment" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ roleId: "role-1", scopeType: "global" }));
  });
});
