import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GroupList } from "@/features/infrastructure/components/group-list";
import { useGroups } from "@/features/infrastructure/hooks/use-groups";
import type { AssetGroup } from "@/features/infrastructure/types";

vi.mock("@/features/infrastructure/hooks/use-groups", () => ({ useGroups: vi.fn() }));

const mocked = vi.mocked(useGroups);

const GROUP: AssetGroup = {
  id: "g1",
  organizationId: "org-1",
  name: "Production web tier",
  description: "All production-facing web servers.",
  groupType: "static",
  rule: {},
  memberAssetIds: ["a1", "a2"],
};

describe("GroupList", () => {
  it("shows a positive empty state when no groups exist yet", () => {
    mocked.mockReturnValue({ data: [], isLoading: false, isError: false } as unknown as ReturnType<typeof useGroups>);
    render(<GroupList organizationId="org-1" onSelect={vi.fn()} />);

    expect(screen.getByText("No groups yet")).toBeInTheDocument();
  });

  it("renders each group's real member count from member_asset_ids, not a fabricated total", () => {
    mocked.mockReturnValue({ data: [GROUP], isLoading: false, isError: false } as unknown as ReturnType<typeof useGroups>);
    render(<GroupList organizationId="org-1" onSelect={vi.fn()} />);

    expect(screen.getByText("Production web tier")).toBeInTheDocument();
    expect(screen.getByText("2 members")).toBeInTheDocument();
  });

  it("calls onSelect with the real group when clicked, to open its members", () => {
    const onSelect = vi.fn();
    mocked.mockReturnValue({ data: [GROUP], isLoading: false, isError: false } as unknown as ReturnType<typeof useGroups>);
    render(<GroupList organizationId="org-1" onSelect={onSelect} />);

    fireEvent.click(screen.getByText("Production web tier"));
    expect(onSelect).toHaveBeenCalledWith(GROUP);
  });
});
