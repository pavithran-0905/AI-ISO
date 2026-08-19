import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TeamFormDialog } from "@/features/administration/components/team-form-dialog";
import { useCreateTeam, useUpdateTeam } from "@/features/administration/hooks/use-teams";
import type { Team } from "@/features/administration/types";

vi.mock("@/features/administration/hooks/use-teams", () => ({ useCreateTeam: vi.fn(), useUpdateTeam: vi.fn(), useRemoveTeam: vi.fn() }));

const TEAM: Team = {
  id: "t1",
  organizationId: "org-1",
  name: "Platform",
  code: "PLAT",
  description: "The platform team.",
  departmentId: null,
  businessUnitId: null,
  teamLeadId: null,
  metadata: {},
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("TeamFormDialog", () => {
  it("starts empty in create mode and calls create with organizationId", async () => {
    const createMutateAsync = vi.fn().mockResolvedValue(TEAM);
    vi.mocked(useCreateTeam).mockReturnValue({ mutateAsync: createMutateAsync, isPending: false } as unknown as ReturnType<typeof useCreateTeam>);
    vi.mocked(useUpdateTeam).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useUpdateTeam>);

    render(<TeamFormDialog organizationId="org-1" team={null} open onClose={vi.fn()} />);
    expect(screen.getByLabelText("Name*")).toHaveValue("");

    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "New Team" } });
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await vi.waitFor(() => expect(createMutateAsync).toHaveBeenCalledWith({ organizationId: "org-1", name: "New Team", code: undefined, description: undefined }));
  });

  it("pre-fills from the given team in edit mode and calls update with its id", async () => {
    const updateMutateAsync = vi.fn().mockResolvedValue(TEAM);
    vi.mocked(useCreateTeam).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useCreateTeam>);
    vi.mocked(useUpdateTeam).mockReturnValue({ mutateAsync: updateMutateAsync, isPending: false } as unknown as ReturnType<typeof useUpdateTeam>);

    render(<TeamFormDialog organizationId="org-1" team={TEAM} open onClose={vi.fn()} />);
    expect(screen.getByLabelText("Name*")).toHaveValue("Platform");

    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "Platform Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await vi.waitFor(() =>
      expect(updateMutateAsync).toHaveBeenCalledWith({ teamId: "t1", input: { name: "Platform Renamed", code: "PLAT", description: "The platform team." } }),
    );
  });
});
