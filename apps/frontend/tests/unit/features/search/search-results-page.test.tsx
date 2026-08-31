import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchResultsPage } from "@/features/search/pages/search-results-page";
import { useGlobalSearch } from "@/features/search/hooks/use-global-search";
import type { SearchResultGroup } from "@/features/search/types";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/search",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
}));
vi.mock("@/features/search/hooks/use-global-search", () => ({ useGlobalSearch: vi.fn() }));

function mockResult(overrides: Partial<SearchResultGroup> = {}): SearchResultGroup[] {
  return [
    {
      type: "asset",
      label: "Assets",
      results: [{ id: "a1", resultType: "asset", title: "edge-01", description: "physical_server", status: "Managed", href: "/infrastructure/assets/a1" }],
      isLoading: false,
      isError: false,
      ...overrides,
    },
  ];
}

describe("SearchResultsPage", () => {
  afterEach(() => {
    push.mockClear();
    mockSearch.current = "";
  });

  it("prompts for a query when none is in the URL", () => {
    vi.mocked(useGlobalSearch).mockReturnValue({ groups: [], isSearching: false, queryLongEnough: false, orgReady: true });
    render(<SearchResultsPage />);
    expect(screen.getByText("Search AI-IOS")).toBeInTheDocument();
  });

  it("renders real grouped results for a URL query and links each result to its real route", () => {
    mockSearch.current = "q=edge";
    vi.mocked(useGlobalSearch).mockReturnValue({ groups: mockResult(), isSearching: false, queryLongEnough: true, orgReady: true });
    render(<SearchResultsPage />);

    expect(screen.getByRole("link", { name: /edge-01/ })).toHaveAttribute("href", "/infrastructure/assets/a1");
  });

  it("shows an empty state for a query with zero real results, never blaming a technical error", () => {
    mockSearch.current = "q=nonexistent";
    vi.mocked(useGlobalSearch).mockReturnValue({ groups: [], isSearching: false, queryLongEnough: true, orgReady: true });
    render(<SearchResultsPage />);

    expect(screen.getByText(/No results for "nonexistent"/)).toBeInTheDocument();
  });

  it("flags a failed group while still rendering the successful ones (partial failure)", () => {
    mockSearch.current = "q=edge";
    vi.mocked(useGlobalSearch).mockReturnValue({
      groups: [...mockResult(), { type: "report", label: "Reports", results: [], isLoading: false, isError: true }],
      isSearching: false,
      queryLongEnough: true,
      orgReady: true,
    });
    render(<SearchResultsPage />);

    expect(screen.getByRole("link", { name: /edge-01/ })).toBeInTheDocument();
    expect(screen.getByText("Temporarily unavailable")).toBeInTheDocument();
  });

  it("narrows to one resource type via the scope selector", () => {
    mockSearch.current = "q=edge";
    vi.mocked(useGlobalSearch).mockReturnValue({
      groups: [...mockResult(), { type: "report", label: "Reports", results: [{ id: "r1", resultType: "report", title: "Weekly report", description: null, status: "Enabled", href: "/reporting/reports/r1" }], isLoading: false, isError: false }],
      isSearching: false,
      queryLongEnough: true,
      orgReady: true,
    });
    render(<SearchResultsPage />);

    fireEvent.click(screen.getByRole("button", { name: /Reports \(1\)/ }));
    expect(push).toHaveBeenCalledWith("/search?q=edge&scope=report");
  });

  it("offers an Ask AI link for the current query", () => {
    mockSearch.current = "q=edge";
    vi.mocked(useGlobalSearch).mockReturnValue({ groups: mockResult(), isSearching: false, queryLongEnough: true, orgReady: true });
    render(<SearchResultsPage />);

    expect(screen.getByRole("link", { name: /Ask AI about/ })).toHaveAttribute("href", "/intelligence/assistant?draft=edge");
  });
});
