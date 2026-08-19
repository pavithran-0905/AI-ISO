import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetFilters, EMPTY_FILTERS } from "@/features/infrastructure/components/asset-filters";
import { useTableDensityStore } from "@/state/table-density-store";

describe("AssetFilters", () => {
  afterEach(() => {
    useTableDensityStore.setState({ density: "comfortable" });
  });

  it("reports search input changes", () => {
    const onChange = vi.fn();
    render(<AssetFilters values={EMPTY_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "db-01" } });

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, query: "db-01" });
  });

  it("hides the reset control until a filter is active, then shows the active count", () => {
    const { rerender } = render(<AssetFilters values={EMPTY_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /reset/i })).not.toBeInTheDocument();

    rerender(
      <AssetFilters values={{ query: "db", status: "managed", assetType: "" }} onChange={vi.fn()} onReset={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("calls onReset when the reset button is clicked", () => {
    const onReset = vi.fn();
    render(
      <AssetFilters values={{ query: "db", status: "", assetType: "" }} onChange={vi.fn()} onReset={onReset} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("toggles table density and persists the preference", () => {
    render(<AssetFilters values={EMPTY_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Compact density" }));

    expect(useTableDensityStore.getState().density).toBe("compact");
  });
});
