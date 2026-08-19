"use client";

import { Box, Maximize2, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import { useMemo, useRef, useState } from "react";

import { StatusIndicator } from "@/components/data-display/status-indicator";
import { IconButton } from "@/components/ui/icon-button";
import { ASSET_HEALTH_TO_STATUS } from "@/features/infrastructure/lib/status-maps";
import type { TopologyGraph, TopologySelection } from "@/features/infrastructure/types";
import { cn } from "@/utils/cn";

const CANVAS_WIDTH = 800;
const CANVAS_HEIGHT = 480;
const RADIUS = 190;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.5;

interface NodePosition {
  id: string;
  x: number;
  y: number;
}

function layoutRadial(graph: TopologyGraph): NodePosition[] {
  const centerX = CANVAS_WIDTH / 2;
  const centerY = CANVAS_HEIGHT / 2;
  const others = graph.nodes.filter((node) => !node.isRoot);
  const positions: NodePosition[] = [{ id: graph.rootId, x: centerX, y: centerY }];
  others.forEach((node, index) => {
    const angle = (index / Math.max(others.length, 1)) * 2 * Math.PI - Math.PI / 2;
    positions.push({ id: node.id, x: centerX + RADIUS * Math.cos(angle), y: centerY + RADIUS * Math.sin(angle) });
  });
  return positions;
}

/**
 * A hand-rolled radial graph canvas — §53 requires checking for an
 * existing graph library and only adding one if genuinely required;
 * the graph this feature ever renders is always exactly one root plus
 * its direct neighbors (see `TopologyGraph`'s own docstring on why
 * multi-hop edges can't be drawn honestly), a shape simple enough that
 * reactflow/cytoscape/d3-force would be pure bundle weight for
 * geometry this straightforward. Real HTML `<button>`s for every node
 * and edge (never a bare SVG shape with a click handler), so each is
 * independently keyboard- and screen-reader-reachable; the SVG layer
 * beneath them is purely decorative (`aria-hidden`) and only draws the
 * connecting lines.
 */
export function TopologyGraphCanvas({
  graph,
  visibleAssetTypes,
  selection,
  onSelectNode,
  onSelectEdge,
}: {
  graph: TopologyGraph;
  visibleAssetTypes: ReadonlySet<string> | null;
  selection: TopologySelection;
  onSelectNode: (id: string) => void;
  onSelectEdge: (id: string) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragState = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);

  const positions = useMemo(() => {
    const map = new Map<string, NodePosition>();
    for (const position of layoutRadial(graph)) map.set(position.id, position);
    return map;
  }, [graph]);

  const visibleNodeIds = useMemo(() => {
    if (!visibleAssetTypes) return new Set(graph.nodes.map((node) => node.id));
    return new Set(
      graph.nodes.filter((node) => node.isRoot || visibleAssetTypes.has(node.assetType)).map((node) => node.id),
    );
  }, [graph.nodes, visibleAssetTypes]);

  const visibleEdges = graph.edges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target));
  const rootName = graph.nodes.find((node) => node.isRoot)?.name ?? "the selected asset";

  function zoomBy(delta: number) {
    setZoom((current) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number((current + delta).toFixed(2)))));
  }

  function fitToScreen() {
    setZoom(graph.nodes.length > 8 ? 0.7 : 1);
    setPan({ x: 0, y: 0 });
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    // A node/edge button starting drag-panning here would capture the
    // subsequent pointerup on this container instead of the button,
    // which suppresses the browser's own click-event synthesis on the
    // original target — real Chromium behavior a jsdom `fireEvent.click`
    // never exercises. Only pan when the gesture starts on empty canvas.
    if ((event.target as HTMLElement).closest("button")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragState.current = { startX: event.clientX, startY: event.clientY, originX: pan.x, originY: pan.y };
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragState.current) return;
    setPan({
      x: dragState.current.originX + (event.clientX - dragState.current.startX),
      y: dragState.current.originY + (event.clientY - dragState.current.startY),
    });
  }

  function handlePointerUp() {
    dragState.current = null;
  }

  function handleWheel(event: ReactWheelEvent<HTMLDivElement>) {
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? -0.1 : 0.1);
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-end gap-1">
        <IconButton icon={ZoomOut} aria-label="Zoom out" variant="outline" onClick={() => zoomBy(-0.2)} />
        <IconButton icon={ZoomIn} aria-label="Zoom in" variant="outline" onClick={() => zoomBy(0.2)} />
        <IconButton icon={Maximize2} aria-label="Fit to screen" variant="outline" onClick={fitToScreen} />
        <IconButton icon={RotateCcw} aria-label="Reset view" variant="outline" onClick={resetView} />
      </div>

      <p className="sr-only">
        Graph centered on {rootName}, showing {visibleNodeIds.size - 1} direct relationship
        {visibleNodeIds.size - 1 === 1 ? "" : "s"}. Each asset and relationship below is a separate focusable control.
        A structured list alternative is available via the List view toggle above.
      </p>

      <div
        className="border-border bg-muted/20 relative h-[420px] w-full touch-none overflow-hidden rounded-lg border"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <div
          className="absolute top-0 left-0 origin-top-left"
          style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
        >
          <svg width={CANVAS_WIDTH} height={CANVAS_HEIGHT} className="absolute top-0 left-0" aria-hidden="true" focusable="false">
            <defs>
              <marker id="topology-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 Z" className="fill-muted-foreground" />
              </marker>
            </defs>
            {visibleEdges.map((edge) => {
              const source = positions.get(edge.source);
              const target = positions.get(edge.target);
              if (!source || !target) return null;
              const isSelected = selection?.kind === "edge" && selection.id === edge.id;
              return (
                <line
                  key={edge.id}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  className={cn("stroke-muted-foreground", isSelected && "stroke-primary")}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  markerEnd="url(#topology-arrow)"
                />
              );
            })}
          </svg>

          {graph.nodes
            .filter((node) => visibleNodeIds.has(node.id))
            .map((node) => {
              const position = positions.get(node.id);
              if (!position) return null;
              const isSelected = selection?.kind === "node" && selection.id === node.id;
              return (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => onSelectNode(node.id)}
                  aria-pressed={isSelected}
                  className={cn(
                    "bg-card absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 rounded-lg border px-3 py-2 text-center shadow-sm transition-colors",
                    "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                    node.isRoot ? "border-primary ring-primary/30 w-32 ring-2" : "border-border w-28 hover:border-muted-foreground/50",
                    isSelected && !node.isRoot && "border-primary",
                  )}
                  style={{ left: position.x, top: position.y }}
                >
                  <Box className="text-muted-foreground size-4" aria-hidden="true" />
                  <span className="w-full truncate text-xs font-medium">{node.name}</span>
                  <span className="text-muted-foreground w-full truncate text-[10px]">{node.assetType}</span>
                  <StatusIndicator state={ASSET_HEALTH_TO_STATUS[node.health ?? "unknown"]} className="text-[10px]" />
                  {node.isRoot && <span className="text-primary text-[10px] font-semibold">FOCUSED</span>}
                </button>
              );
            })}

          {visibleEdges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const sourceName = graph.nodes.find((node) => node.id === edge.source)?.name ?? edge.source;
            const targetName = graph.nodes.find((node) => node.id === edge.target)?.name ?? edge.target;
            const isSelected = selection?.kind === "edge" && selection.id === edge.id;
            return (
              <button
                key={edge.id}
                type="button"
                onClick={() => onSelectEdge(edge.id)}
                aria-label={`Relationship: ${edge.relationshipType}, from ${sourceName} to ${targetName}`}
                aria-pressed={isSelected}
                className={cn(
                  "bg-card border-border text-muted-foreground absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-1.5 py-0.5 text-[10px] font-medium shadow-sm transition-colors",
                  "hover:text-foreground focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                  isSelected && "border-primary text-primary",
                )}
                style={{ left: (source.x + target.x) / 2, top: (source.y + target.y) / 2 }}
              >
                {edge.relationshipType}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
