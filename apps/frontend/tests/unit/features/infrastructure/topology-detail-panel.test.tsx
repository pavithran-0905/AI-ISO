import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopologyDetailPanel } from "@/features/infrastructure/components/topology-detail-panel";
import { useAssetRelationships } from "@/features/infrastructure/hooks/use-relationships";
import type { TopologyGraph } from "@/features/infrastructure/types";

vi.mock("@/features/infrastructure/hooks/use-relationships", () => ({ useAssetRelationships: vi.fn() }));

const GRAPH: TopologyGraph = {
  rootId: "root",
  nodes: [
    { id: "root", name: "web-01", assetType: "web_server", health: "healthy", isRoot: true },
    { id: "db", name: "db-01", assetType: "database", health: "critical", isRoot: false },
  ],
  edges: [{ id: "root::depends_on::db", source: "root", target: "db", relationshipType: "depends_on" }],
};

function mockRelationships(data: unknown = []) {
  vi.mocked(useAssetRelationships).mockReturnValue({ data, isLoading: false } as unknown as ReturnType<typeof useAssetRelationships>);
}

describe("TopologyDetailPanel", () => {
  it("renders nothing when there is no selection", () => {
    mockRelationships();
    const { container } = render(
      <TopologyDetailPanel graph={GRAPH} selection={null} onClose={vi.fn()} onSelectNode={vi.fn()} onFocusAsset={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("offers to focus on a non-root neighbor, but not on the root itself", () => {
    mockRelationships();
    const { rerender } = render(
      <TopologyDetailPanel graph={GRAPH} selection={{ kind: "node", id: "db" }} onClose={vi.fn()} onSelectNode={vi.fn()} onFocusAsset={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Focus topology on this asset" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full asset detail" })).toHaveAttribute("href", "/infrastructure/assets/db");

    rerender(
      <TopologyDetailPanel graph={GRAPH} selection={{ kind: "node", id: "root" }} onClose={vi.fn()} onSelectNode={vi.fn()} onFocusAsset={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: "Focus topology on this asset" })).not.toBeInTheDocument();
    expect(screen.getByText("Focused asset")).toBeInTheDocument();
  });

  it("calls onFocusAsset with the node's id when the focus action is used", () => {
    mockRelationships();
    const onFocusAsset = vi.fn();
    render(
      <TopologyDetailPanel graph={GRAPH} selection={{ kind: "node", id: "db" }} onClose={vi.fn()} onSelectNode={vi.fn()} onFocusAsset={onFocusAsset} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Focus topology on this asset" }));
    expect(onFocusAsset).toHaveBeenCalledWith("db");
  });

  it("shows the relationship type and both endpoint names for an edge selection", () => {
    mockRelationships();
    render(
      <TopologyDetailPanel
        graph={GRAPH}
        selection={{ kind: "edge", id: "root::depends_on::db" }}
        onClose={vi.fn()}
        onSelectNode={vi.fn()}
        onFocusAsset={vi.fn()}
      />,
    );
    expect(screen.getByText("depends_on")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "web-01" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "db-01" })).toBeInTheDocument();
  });

  it("masks a sensitive-looking metadata key when a matching real relationship carries it", () => {
    mockRelationships([
      {
        id: "rel-1",
        organizationId: "org-1",
        sourceAssetId: "root",
        targetAssetId: "db",
        relationshipType: "depends_on",
        customLabel: "primary link",
        metadata: { api_key: "sk-should-not-render-raw", note: "public note" },
      },
    ]);
    render(
      <TopologyDetailPanel
        graph={GRAPH}
        selection={{ kind: "edge", id: "root::depends_on::db" }}
        onClose={vi.fn()}
        onSelectNode={vi.fn()}
        onFocusAsset={vi.fn()}
      />,
    );
    expect(screen.getByText("primary link")).toBeInTheDocument();
    expect(screen.getByText("public note")).toBeInTheDocument();
    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.queryByText(/sk-should-not-render-raw/)).not.toBeInTheDocument();
  });

  it("says plainly when no real relationship metadata is recorded, rather than inventing any", () => {
    mockRelationships([]);
    render(
      <TopologyDetailPanel
        graph={GRAPH}
        selection={{ kind: "edge", id: "root::depends_on::db" }}
        onClose={vi.fn()}
        onSelectNode={vi.fn()}
        onFocusAsset={vi.fn()}
      />,
    );
    expect(screen.getByText("No additional metadata recorded for this relationship.")).toBeInTheDocument();
  });
});
