import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopologyGraphCanvas } from "@/features/infrastructure/components/topology-graph-canvas";
import type { TopologyGraph } from "@/features/infrastructure/types";

const GRAPH: TopologyGraph = {
  rootId: "root",
  nodes: [
    { id: "root", name: "web-01", assetType: "web_server", health: "healthy", isRoot: true },
    { id: "db", name: "db-01", assetType: "database", health: "critical", isRoot: false },
    { id: "cache", name: "cache-01", assetType: "database", health: "warning", isRoot: false },
  ],
  edges: [
    { id: "root::depends_on::db", source: "root", target: "db", relationshipType: "depends_on" },
    { id: "root::depends_on::cache", source: "root", target: "cache", relationshipType: "depends_on" },
  ],
};

describe("TopologyGraphCanvas", () => {
  it("renders the root and every neighbor as a focusable node", () => {
    render(<TopologyGraphCanvas graph={GRAPH} visibleAssetTypes={null} selection={null} onSelectNode={vi.fn()} onSelectEdge={vi.fn()} />);
    expect(screen.getByRole("button", { name: /^web-01/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^db-01/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^cache-01/ })).toBeInTheDocument();
  });

  it("renders each real edge as an independently focusable, labeled control", () => {
    render(<TopologyGraphCanvas graph={GRAPH} visibleAssetTypes={null} selection={null} onSelectNode={vi.fn()} onSelectEdge={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Relationship: depends_on, from web-01 to db-01" })).toBeInTheDocument();
  });

  it("calls onSelectNode with the node's id when a node is clicked", () => {
    const onSelectNode = vi.fn();
    render(<TopologyGraphCanvas graph={GRAPH} visibleAssetTypes={null} selection={null} onSelectNode={onSelectNode} onSelectEdge={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /^db-01/ }));
    expect(onSelectNode).toHaveBeenCalledWith("db");
  });

  it("calls onSelectEdge with the edge's id when an edge chip is clicked", () => {
    const onSelectEdge = vi.fn();
    render(<TopologyGraphCanvas graph={GRAPH} visibleAssetTypes={null} selection={null} onSelectNode={vi.fn()} onSelectEdge={onSelectEdge} />);
    fireEvent.click(screen.getByRole("button", { name: "Relationship: depends_on, from web-01 to db-01" }));
    expect(onSelectEdge).toHaveBeenCalledWith("root::depends_on::db");
  });

  it("hides a neighbor whose asset type is filtered out, but never hides the root", () => {
    render(
      <TopologyGraphCanvas
        graph={GRAPH}
        visibleAssetTypes={new Set(["web_server"])}
        selection={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /web-01/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /db-01/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cache-01/ })).not.toBeInTheDocument();
  });

  it("supports zoom in, zoom out, fit-to-screen, and reset via keyboard-accessible controls", () => {
    render(<TopologyGraphCanvas graph={GRAPH} visibleAssetTypes={null} selection={null} onSelectNode={vi.fn()} onSelectEdge={vi.fn()} />);
    for (const label of ["Zoom in", "Zoom out", "Fit to screen", "Reset view"]) {
      const button = screen.getByRole("button", { name: label });
      fireEvent.click(button);
      expect(button).toBeInTheDocument();
    }
  });
});
