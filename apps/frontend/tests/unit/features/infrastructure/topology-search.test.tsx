import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TopologySearch } from "@/features/infrastructure/components/topology-search";
import { useAssetSearch } from "@/features/infrastructure/hooks/use-assets";

vi.mock("@/features/infrastructure/hooks/use-assets", () => ({ useAssetSearch: vi.fn() }));

describe("TopologySearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not query until at least 2 characters have settled past the debounce", () => {
    vi.mocked(useAssetSearch).mockReturnValue({ data: undefined, isLoading: false, isError: false } as unknown as ReturnType<typeof useAssetSearch>);
    render(<TopologySearch organizationId="org-1" onFocusAsset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Search assets"), { target: { value: "d" } });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(useAssetSearch).toHaveBeenLastCalledWith(null);
  });

  it("queries once 2+ characters have settled past the debounce", () => {
    vi.mocked(useAssetSearch).mockReturnValue({
      data: { items: [{ id: "db1", name: "db-01", displayName: "db-01", assetType: "database" }], pagination: {} },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAssetSearch>);
    render(<TopologySearch organizationId="org-1" onFocusAsset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Search assets"), { target: { value: "db" } });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(useAssetSearch).toHaveBeenLastCalledWith({ organizationId: "org-1", query: "db", page: 1, pageSize: 8 });
    expect(screen.getByRole("button", { name: /db-01/ })).toBeInTheDocument();
  });

  it("calls onFocusAsset with the selected result's id and clears the input", () => {
    vi.mocked(useAssetSearch).mockReturnValue({
      data: { items: [{ id: "db1", name: "db-01", displayName: "db-01", assetType: "database" }], pagination: {} },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAssetSearch>);
    const onFocusAsset = vi.fn();
    render(<TopologySearch organizationId="org-1" onFocusAsset={onFocusAsset} />);

    const input = screen.getByLabelText("Search assets");
    fireEvent.change(input, { target: { value: "db" } });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    fireEvent.click(screen.getByRole("button", { name: /db-01/ }));

    expect(onFocusAsset).toHaveBeenCalledWith("db1");
    expect(input).toHaveValue("");
  });
});
