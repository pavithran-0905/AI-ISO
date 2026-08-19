import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopologyListView } from "@/features/infrastructure/components/topology-list-view";
import { useTopology } from "@/features/infrastructure/hooks/use-topology";

vi.mock("@/features/infrastructure/hooks/use-topology", () => ({ useTopology: vi.fn() }));

function mockTopology(nodes: unknown[] = []) {
  vi.mocked(useTopology).mockReturnValue({
    data: { rootAssetId: "root", queryKind: "neighbors", nodes },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useTopology>);
}

describe("TopologyListView", () => {
  it("hides the depth control on the Neighbors tab, since the backend ignores depth for it", () => {
    mockTopology();
    render(<TopologyListView assetId="root" onFocusAsset={vi.fn()} />);
    expect(screen.queryByLabelText("Depth")).not.toBeInTheDocument();
    expect(screen.getByText(/depth doesn't apply to this view/)).toBeInTheDocument();
  });

  it("shows a real depth selector on the Dependencies and Impact tabs", () => {
    mockTopology();
    render(<TopologyListView assetId="root" onFocusAsset={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Dependencies" }));
    expect(screen.getByLabelText("Depth")).toBeInTheDocument();
    expect(useTopology).toHaveBeenLastCalledWith("root", "dependencies", 2);
  });

  it("passes the selected depth through to the query", () => {
    mockTopology();
    render(<TopologyListView assetId="root" onFocusAsset={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Impact" }));
    fireEvent.change(screen.getByLabelText("Depth"), { target: { value: "4" } });
    expect(useTopology).toHaveBeenLastCalledWith("root", "impact", 4);
  });

  it("renders each result with its distance and lets the caller focus on it", () => {
    mockTopology([{ id: "db", name: "db-01", assetType: "database", distance: 2, relationshipType: null, outgoing: null }]);
    const onFocusAsset = vi.fn();
    render(<TopologyListView assetId="root" onFocusAsset={onFocusAsset} />);

    expect(screen.getByText(/2 hops/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Focus" }));
    expect(onFocusAsset).toHaveBeenCalledWith("db");
  });

  it("labels an incoming relationship distinctly from an outgoing one", () => {
    mockTopology([{ id: "lb", name: "lb-01", assetType: "load_balancer", distance: 1, relationshipType: "depends_on", outgoing: false }]);
    render(<TopologyListView assetId="root" onFocusAsset={vi.fn()} />);
    expect(screen.getByText(/depends_on \(incoming\)/)).toBeInTheDocument();
  });
});
