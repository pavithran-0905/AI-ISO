"use client";

import { LayoutList, Share2 } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { TopologyDetailPanel } from "@/features/infrastructure/components/topology-detail-panel";
import { TopologyFilters } from "@/features/infrastructure/components/topology-filters";
import { TopologyGraphCanvas } from "@/features/infrastructure/components/topology-graph-canvas";
import { TopologyLegend } from "@/features/infrastructure/components/topology-legend";
import { TopologyListView } from "@/features/infrastructure/components/topology-list-view";
import { TopologySearch } from "@/features/infrastructure/components/topology-search";
import { useTopologyGraph } from "@/features/infrastructure/hooks/use-topology-graph";
import type { TopologyGraph, TopologySelection } from "@/features/infrastructure/types";

const MOBILE_QUERY = "(max-width: 767px)";

function subscribeToMobileQuery(callback: () => void) {
  const query = window.matchMedia(MOBILE_QUERY);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

function getIsMobileSnapshot() {
  return window.matchMedia(MOBILE_QUERY).matches;
}

function getIsMobileServerSnapshot() {
  return false;
}

/** Mirrors Tailwind's own `md` breakpoint (768px) — §45: "do not
 * attempt to squeeze the complete desktop graph into mobile," so below
 * it the workspace always renders the list view, never the canvas,
 * regardless of the `view` toggle's own state. `useSyncExternalStore`
 * subscribes to the browser's own `matchMedia` change event directly,
 * rather than an effect that calls `setState` on mount (an
 * anti-pattern this app's lint config rejects). */
function useIsMobileViewport(): boolean {
  return useSyncExternalStore(subscribeToMobileQuery, getIsMobileSnapshot, getIsMobileServerSnapshot);
}

/**
 * §4 "Topology Overview" — search/view-toggle header, canvas or list,
 * filters/legend sidebar, and a selection detail drawer, adapted from
 * the prompt's own ASCII layout onto this app's existing shell
 * primitives (§46).
 */
export function TopologyWorkspace({
  organizationId,
  focusAssetId,
  view,
  onFocusAsset,
  onViewChange,
}: {
  organizationId: string;
  focusAssetId: string | null;
  view: "graph" | "list";
  onFocusAsset: (assetId: string) => void;
  onViewChange: (view: "graph" | "list") => void;
}) {
  const isMobile = useIsMobileViewport();
  const { graph, isLoading, isError, error, refetch } = useTopologyGraph(focusAssetId, organizationId);
  const effectiveView = isMobile ? "list" : view;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="w-full max-w-sm">
          <TopologySearch organizationId={organizationId} onFocusAsset={onFocusAsset} />
        </div>
        {!isMobile && focusAssetId && (
          <div className="flex items-center gap-1" role="group" aria-label="Topology view">
            <IconButton
              icon={Share2}
              aria-label="Graph view"
              aria-pressed={view === "graph"}
              variant={view === "graph" ? "secondary" : "outline"}
              onClick={() => onViewChange("graph")}
            />
            <IconButton
              icon={LayoutList}
              aria-label="List view"
              aria-pressed={view === "list"}
              variant={view === "list" ? "secondary" : "outline"}
              onClick={() => onViewChange("list")}
            />
          </div>
        )}
      </div>

      {!focusAssetId && (
        <EmptyState
          title="Choose an asset to explore its topology"
          description="Search for an asset above, or open “View in topology” from any asset's own detail page."
        />
      )}

      {focusAssetId && (
        <SectionState isLoading={isLoading} isError={isError} error={error} onRetry={refetch} skeletonClassName="h-96 w-full">
          {graph && (
            // `key`ed by focus so selection/filter state resets to a
            // clean slate when the focused asset changes, instead of
            // an effect syncing it after the fact.
            <TopologyFocusedGraph key={focusAssetId} graph={graph} view={effectiveView} focusAssetId={focusAssetId} onFocusAsset={onFocusAsset} />
          )}
        </SectionState>
      )}
    </div>
  );
}

function TopologyFocusedGraph({
  graph,
  view,
  focusAssetId,
  onFocusAsset,
}: {
  graph: TopologyGraph;
  view: "graph" | "list";
  focusAssetId: string;
  onFocusAsset: (assetId: string) => void;
}) {
  const [selection, setSelection] = useState<TopologySelection>(null);
  const [visibleAssetTypes, setVisibleAssetTypes] = useState<ReadonlySet<string> | null>(null);

  return (
    <div className="flex flex-col gap-4">
      {view === "list" ? (
        <TopologyListView assetId={focusAssetId} onFocusAsset={onFocusAsset} />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_220px]">
          <TopologyGraphCanvas
            graph={graph}
            visibleAssetTypes={visibleAssetTypes}
            selection={selection}
            onSelectNode={(id) => setSelection({ kind: "node", id })}
            onSelectEdge={(id) => setSelection({ kind: "edge", id })}
          />
          <div className="flex flex-col gap-4">
            <TopologyFilters graph={graph} visibleAssetTypes={visibleAssetTypes} onChange={setVisibleAssetTypes} />
            <TopologyLegend />
          </div>
        </div>
      )}

      <TopologyDetailPanel
        graph={graph}
        selection={selection}
        onClose={() => setSelection(null)}
        onSelectNode={(id) => setSelection({ kind: "node", id })}
        onFocusAsset={onFocusAsset}
      />
    </div>
  );
}
