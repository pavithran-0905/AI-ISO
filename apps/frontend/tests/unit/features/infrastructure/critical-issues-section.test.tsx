import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CriticalIssuesSection } from "@/features/infrastructure/components/critical-issues-section";
import { useAssetSearch } from "@/features/infrastructure/hooks/use-assets";

vi.mock("@/features/infrastructure/hooks/use-assets", () => ({
  useAssetSearch: vi.fn(),
}));

const mocked = vi.mocked(useAssetSearch);

function asset(overrides: Record<string, unknown>) {
  return { id: "a1", name: "asset-1", displayName: null, health: "healthy", ...overrides };
}

describe("CriticalIssuesSection", () => {
  it("shows only assets whose health is critical or unreachable, not every asset", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          asset({ id: "a1", name: "Healthy One", health: "healthy" }),
          asset({ id: "a2", name: "Critical One", health: "critical" }),
          asset({ id: "a3", name: "Unreachable One", health: "unreachable" }),
        ],
        pagination: { total: 3, page: 1, pageSize: 100, totalPages: 1, hasNext: false, hasPrevious: false },
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAssetSearch>);

    render(<CriticalIssuesSection organizationId="org-1" />);

    expect(screen.getByText("Critical One")).toBeInTheDocument();
    expect(screen.getByText("Unreachable One")).toBeInTheDocument();
    expect(screen.queryByText("Healthy One")).not.toBeInTheDocument();
  });

  it("shows a positive empty state when nothing is critical", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [asset({ health: "healthy" })],
        pagination: { total: 1, page: 1, pageSize: 100, totalPages: 1, hasNext: false, hasPrevious: false },
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAssetSearch>);

    render(<CriticalIssuesSection organizationId="org-1" />);

    expect(screen.getByText("No critical issues")).toBeInTheDocument();
  });

  it("notes when the scan was truncated to one page of a larger dataset", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [asset({ health: "critical" })],
        pagination: { total: 500, page: 1, pageSize: 100, totalPages: 5, hasNext: true, hasPrevious: false },
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAssetSearch>);

    render(<CriticalIssuesSection organizationId="org-1" />);

    expect(screen.getByText(/Scanned the 100 most recently updated assets/)).toBeInTheDocument();
  });
});
