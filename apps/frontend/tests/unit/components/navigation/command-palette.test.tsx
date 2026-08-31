import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "@/components/navigation/command-palette";
import { useGlobalSearch } from "@/features/search/hooks/use-global-search";
import { usePermissions } from "@/permissions/hooks";
import { useCommandPaletteStore } from "@/state/command-palette-store";
import { useRecentSearchesStore } from "@/state/recent-searches-store";
import type { SearchResultGroup } from "@/features/search/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));
vi.mock("@/permissions/hooks", () => ({ usePermissions: vi.fn() }));
vi.mock("@/features/search/hooks/use-global-search", () => ({ useGlobalSearch: vi.fn() }));

function mockNoResourceResults() {
  vi.mocked(useGlobalSearch).mockReturnValue({ groups: [], isSearching: false, queryLongEnough: false, orgReady: true });
}

function mockAdmin() {
  vi.mocked(usePermissions).mockReturnValue({ role: "super_admin", can: vi.fn(), isReadOnly: false, isAdministrative: true } as unknown as ReturnType<typeof usePermissions>);
}

describe("CommandPalette", () => {
  afterEach(() => {
    useCommandPaletteStore.setState({ open: false });
    useRecentSearchesStore.setState({ terms: [] });
    push.mockClear();
  });

  it("opens in response to the shared store's open flag", () => {
    mockAdmin();
    mockNoResourceResults();
    render(<CommandPalette />);
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");

    act(() => {
      useCommandPaletteStore.getState().show();
    });
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAttribute("open");
  });

  it("opens on Ctrl/Cmd+K from anywhere in the document", () => {
    mockAdmin();
    mockNoResourceResults();
    render(<CommandPalette />);
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(useCommandPaletteStore.getState().open).toBe(true);
  });

  it("lists every implemented route by default and filters as the query changes", () => {
    mockAdmin();
    mockNoResourceResults();
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    expect(screen.getByRole("option", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /design system showcase/i })).toBeInTheDocument();

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "design" } });

    expect(screen.queryByRole("option", { name: /^dashboard/i })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: /design system showcase/i })).toBeInTheDocument();
  });

  it("hides a role-restricted route from a session without that role, the same gating the sidebar applies", () => {
    vi.mocked(usePermissions).mockReturnValue({ role: "operator", can: vi.fn(), isReadOnly: false, isAdministrative: false } as unknown as ReturnType<typeof usePermissions>);
    mockNoResourceResults();
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    expect(screen.queryByRole("option", { name: /^users/i })).not.toBeInTheDocument();
  });

  it("shows an empty state when no command or resource matches the query", () => {
    mockAdmin();
    mockNoResourceResults();
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "nothing matches this" } });
    expect(screen.getByText(/No results for/)).toBeInTheDocument();
  });

  it("navigates to the highlighted result and closes on Enter", () => {
    mockAdmin();
    mockNoResourceResults();
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "design" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(push).toHaveBeenCalledWith("/design-system");
    expect(useCommandPaletteStore.getState().open).toBe(false);
  });

  it("moves the active option with ArrowDown/ArrowUp", () => {
    mockAdmin();
    mockNoResourceResults();
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    const input = screen.getByRole("combobox");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(options[1]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(options[0]).toHaveAttribute("aria-selected", "true");
  });

  it("groups real resource results by type, navigates to a result's own real route, and flags a failed group without hiding the rest", () => {
    mockAdmin();
    const groups: SearchResultGroup[] = [
      {
        type: "asset",
        label: "Assets",
        results: [{ id: "a1", resultType: "asset", title: "edge-01", description: "physical_server", status: "Managed", href: "/infrastructure/assets/a1" }],
        isLoading: false,
        isError: false,
      },
      { type: "report", label: "Reports", results: [], isLoading: false, isError: true },
    ];
    vi.mocked(useGlobalSearch).mockReturnValue({ groups, isSearching: false, queryLongEnough: true, orgReady: true });
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "edge" } });
    expect(screen.getByRole("option", { name: /edge-01/ })).toBeInTheDocument();
    expect(screen.getByText(/temporarily unavailable/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("option", { name: /edge-01/ }));
    expect(push).toHaveBeenCalledWith("/infrastructure/assets/a1");
  });

  it("shows recent searches when the query is empty, and clears them on request", () => {
    mockAdmin();
    mockNoResourceResults();
    useRecentSearchesStore.setState({ terms: ["edge-01", "weekly report"] });
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    expect(screen.getByText("edge-01")).toBeInTheDocument();
    expect(screen.getByText("weekly report")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(useRecentSearchesStore.getState().terms).toEqual([]);
  });

  it("offers Ask AI and View all results once a query is typed", () => {
    mockAdmin();
    mockNoResourceResults();
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "edge-01" } });
    expect(screen.getByRole("link", { name: /Ask AI/ })).toHaveAttribute("href", "/intelligence/assistant?draft=edge-01");
    expect(screen.getByRole("link", { name: "View all results" })).toHaveAttribute("href", "/search?q=edge-01");
  });
});
