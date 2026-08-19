import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProjectIdentityForm } from "@/features/settings/components/project-identity-form";
import { usePatchProject } from "@/features/settings/hooks/use-project-settings";
import type { ProjectSummary } from "@/features/settings/types";

vi.mock("@/features/settings/hooks/use-project-settings", () => ({ usePatchProject: vi.fn() }));

const PROJECT: ProjectSummary = {
  id: "p1",
  organizationId: "org-1",
  name: "core-platform",
  displayName: "Core Platform",
  description: "The main project.",
  code: null,
  status: "active",
  ownerId: "u1",
  visibility: "private",
  defaultLanguage: "en",
  timezone: "UTC",
  category: null,
  priority: "medium",
  archivedAt: null,
  metadata: {},
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("ProjectIdentityForm", () => {
  it("sends a genuinely partial PATCH with only the edited fields, using the project's own id", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(PROJECT);
    vi.mocked(usePatchProject).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof usePatchProject>);

    render(<ProjectIdentityForm project={PROJECT} canEdit />);
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Core Platform Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save project" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync).toHaveBeenCalledWith({
      projectId: "p1",
      input: { name: "core-platform", displayName: "Core Platform Renamed", description: "The main project." },
    });
  });

  it("renders read-only when the caller can't edit", () => {
    vi.mocked(usePatchProject).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof usePatchProject>);
    render(<ProjectIdentityForm project={PROJECT} canEdit={false} />);
    expect(screen.getByText("Core Platform")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save project" })).not.toBeInTheDocument();
  });
});
