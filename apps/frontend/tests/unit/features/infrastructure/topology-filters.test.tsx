import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopologyFilters } from "@/features/infrastructure/components/topology-filters";
import type { TopologyGraph } from "@/features/infrastructure/types";

const GRAPH: TopologyGraph = {
  rootId: "root",
  nodes: [
    { id: "root", name: "web-01", assetType: "web_server", health: "healthy", isRoot: true },
    { id: "db", name: "db-01", assetType: "database", health: "critical", isRoot: false },
    { id: "cache", name: "cache-01", assetType: "database", health: "warning", isRoot: false },
  ],
  edges: [],
};

describe("TopologyFilters", () => {
  it("lists each asset type present among the neighbors, excluding the root's own type and duplicates", () => {
    render(<TopologyFilters graph={GRAPH} visibleAssetTypes={null} onChange={vi.fn()} />);
    expect(screen.getByText("database")).toBeInTheDocument();
    expect(screen.queryByText("web_server")).not.toBeInTheDocument();
  });

  it("renders nothing when the focused asset has no neighbors", () => {
    const empty: TopologyGraph = { rootId: "root", nodes: [GRAPH.nodes[0]], edges: [] };
    const { container } = render(<TopologyFilters graph={empty} visibleAssetTypes={null} onChange={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("unchecking the only present type reports an empty visible set", () => {
    const onChange = vi.fn();
    render(<TopologyFilters graph={GRAPH} visibleAssetTypes={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(new Set());
  });

  it("reflects an externally-provided visible set in the checkbox state", () => {
    render(<TopologyFilters graph={GRAPH} visibleAssetTypes={new Set()} onChange={vi.fn()} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });
});
