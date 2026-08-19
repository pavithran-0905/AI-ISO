import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TopologyWorkspace } from "@/features/infrastructure/components/topology-workspace";
import { useAssetSearch } from "@/features/infrastructure/hooks/use-assets";
import { useAssetRelationships } from "@/features/infrastructure/hooks/use-relationships";
import { useTopology } from "@/features/infrastructure/hooks/use-topology";
import { useTopologyGraph } from "@/features/infrastructure/hooks/use-topology-graph";
import type { TopologyGraph } from "@/features/infrastructure/types";

vi.mock("@/features/infrastructure/hooks/use-topology-graph", () => ({ useTopologyGraph: vi.fn() }));
vi.mock("@/features/infrastructure/hooks/use-assets", async () => {
  const actual = await vi.importActual<typeof import("@/features/infrastructure/hooks/use-assets")>("@/features/infrastructure/hooks/use-assets");
  return { ...actual, useAssetSearch: vi.fn() };
});
vi.mock("@/features/infrastructure/hooks/use-relationships", () => ({ useAssetRelationships: vi.fn() }));
vi.mock("@/features/infrastructure/hooks/use-topology", () => ({ useTopology: vi.fn() }));

const GRAPH: TopologyGraph = {
  rootId: "root",
  nodes: [
    { id: "root", name: "web-01", assetType: "web_server", health: "healthy", isRoot: true },
    { id: "db", name: "db-01", assetType: "database", health: "critical", isRoot: false },
  ],
  edges: [{ id: "root::depends_on::db", source: "root", target: "db", relationshipType: "depends_on" }],
};

describe("TopologyWorkspace", () => {
  beforeEach(() => {
    vi.mocked(useAssetSearch).mockReturnValue({ data: undefined, isLoading: false, isError: false } as unknown as ReturnType<typeof useAssetSearch>);
    vi.mocked(useAssetRelationships).mockReturnValue({ data: [], isLoading: false } as unknown as ReturnType<typeof useAssetRelationships>);
    vi.mocked(useTopology).mockReturnValue({
      data: { rootAssetId: "root", queryKind: "neighbors", nodes: [] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTopology>);
  });

  it("prompts to choose an asset before any focus is set, rather than guessing a starting point", () => {
    vi.mocked(useTopologyGraph).mockReturnValue({ graph: null, isLoading: false, isError: false, error: null, refetch: vi.fn() });
    render(<TopologyWorkspace organizationId="org-1" focusAssetId={null} view="graph" onFocusAsset={vi.fn()} onViewChange={vi.fn()} />);
    expect(screen.getByText("Choose an asset to explore its topology")).toBeInTheDocument();
  });

  it("renders the graph canvas once a focused asset's graph has loaded", () => {
    vi.mocked(useTopologyGraph).mockReturnValue({ graph: GRAPH, isLoading: false, isError: false, error: null, refetch: vi.fn() });
    render(<TopologyWorkspace organizationId="org-1" focusAssetId="root" view="graph" onFocusAsset={vi.fn()} onViewChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /^db-01/ })).toBeInTheDocument();
  });

  it("renders the list view instead when view is 'list'", () => {
    vi.mocked(useTopologyGraph).mockReturnValue({ graph: GRAPH, isLoading: false, isError: false, error: null, refetch: vi.fn() });
    render(<TopologyWorkspace organizationId="org-1" focusAssetId="root" view="list" onFocusAsset={vi.fn()} onViewChange={vi.fn()} />);
    expect(screen.getByRole("tablist", { name: "Topology view" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /db-01/ })).not.toBeInTheDocument();
  });

  it("opens the detail panel and calls onFocusAsset when a neighbor's focus action is used", () => {
    vi.mocked(useTopologyGraph).mockReturnValue({ graph: GRAPH, isLoading: false, isError: false, error: null, refetch: vi.fn() });
    const onFocusAsset = vi.fn();
    render(<TopologyWorkspace organizationId="org-1" focusAssetId="root" view="graph" onFocusAsset={onFocusAsset} onViewChange={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /^db-01/ }));
    fireEvent.click(screen.getByRole("button", { name: "Focus topology on this asset" }));
    expect(onFocusAsset).toHaveBeenCalledWith("db");
  });
});
