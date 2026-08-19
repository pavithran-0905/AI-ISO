"use client";

import Link from "next/link";

import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Button, buttonVariants } from "@/components/ui/button";
import { Drawer } from "@/components/overlays/drawer";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { useAssetRelationships } from "@/features/infrastructure/hooks/use-relationships";
import { ASSET_HEALTH_TO_STATUS } from "@/features/infrastructure/lib/status-maps";
import { isSensitiveMetadataKey, maskMetadataValue } from "@/features/infrastructure/lib/sensitive-metadata";
import type { TopologyGraph, TopologySelection } from "@/features/infrastructure/types";
import { cn } from "@/utils/cn";

/**
 * §12 "Detail Panel" — Quick Details → Relationships → Health →
 * Actions, in a drawer rather than navigating away. Only sections
 * backed by real data: no Metrics/Alerts/Automation sections (both
 * confirmed absent for any asset in this backend — see the developer
 * guide), and edge metadata is shown only when a real
 * `AssetRelationship` matching this edge is found (§13: "do not create
 * fake relationship descriptions").
 */
export function TopologyDetailPanel({
  graph,
  selection,
  onClose,
  onSelectNode,
  onFocusAsset,
}: {
  graph: TopologyGraph;
  selection: TopologySelection;
  onClose: () => void;
  onSelectNode: (id: string) => void;
  onFocusAsset: (id: string) => void;
}) {
  const relationshipsQuery = useAssetRelationships(selection ? graph.rootId : null);

  if (!selection) return null;

  if (selection.kind === "node") {
    const node = graph.nodes.find((candidate) => candidate.id === selection.id);
    if (!node) return null;
    const edgesTouchingNode = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id);

    return (
      <Drawer open title={node.name} onClose={onClose}>
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-3">
            <StatusIndicator state={ASSET_HEALTH_TO_STATUS[node.health ?? "unknown"]} />
            <span className="text-muted-foreground text-xs">{node.assetType}</span>
            {node.isRoot && <span className="text-primary text-xs font-semibold">Focused asset</span>}
          </div>

          <div className="flex flex-wrap gap-2">
            {!node.isRoot && (
              <Button onClick={() => onFocusAsset(node.id)} variant="outline">
                Focus topology on this asset
              </Button>
            )}
            <Link href={`/infrastructure/assets/${node.id}`} className={buttonVariants("outline")}>
              Open full asset detail
            </Link>
            <AskAiButton draft={`Tell me about the asset "${node.name}" (id: ${node.id}) and its role in this topology.`} />
          </div>

          <div>
            <p className="mb-2 text-sm font-medium">Relationships</p>
            {edgesTouchingNode.length === 0 ? (
              <p className="text-muted-foreground text-xs">No direct relationships recorded.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {edgesTouchingNode.map((edge) => {
                  const isOutgoing = edge.source === node.id;
                  const neighborId = isOutgoing ? edge.target : edge.source;
                  const neighborName = graph.nodes.find((candidate) => candidate.id === neighborId)?.name ?? neighborId;
                  return (
                    <li key={edge.id} className="text-xs">
                      <span className="text-muted-foreground">{isOutgoing ? edge.relationshipType : `${edge.relationshipType} (incoming)`}</span>{" "}
                      <button type="button" onClick={() => onSelectNode(neighborId)} className="font-medium hover:underline">
                        {neighborName}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {!node.isRoot && (
              <p className="text-muted-foreground mt-2 text-xs">
                Only this asset&apos;s connection to the focused asset is shown here. Focus the topology on it to see its own
                full relationship set.
              </p>
            )}
          </div>
        </div>
      </Drawer>
    );
  }

  const edge = graph.edges.find((candidate) => candidate.id === selection.id);
  if (!edge) return null;
  const sourceName = graph.nodes.find((node) => node.id === edge.source)?.name ?? edge.source;
  const targetName = graph.nodes.find((node) => node.id === edge.target)?.name ?? edge.target;
  const matchingRelationship = (relationshipsQuery.data ?? []).find(
    (relationship) =>
      relationship.sourceAssetId === edge.source &&
      relationship.targetAssetId === edge.target &&
      relationship.relationshipType === edge.relationshipType,
  );
  const metadataEntries = Object.entries(matchingRelationship?.metadata ?? {});

  return (
    <Drawer open title="Relationship" onClose={onClose}>
      <div className="flex flex-col gap-4 text-sm">
        <div>
          <p className="text-muted-foreground text-xs">Type</p>
          <p className="font-medium">{edge.relationshipType}</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => onSelectNode(edge.source)} className="font-medium hover:underline">
            {sourceName}
          </button>
          <span className="text-muted-foreground text-xs">→</span>
          <button type="button" onClick={() => onSelectNode(edge.target)} className="font-medium hover:underline">
            {targetName}
          </button>
        </div>
        {matchingRelationship?.customLabel && (
          <div>
            <p className="text-muted-foreground text-xs">Label</p>
            <p>{matchingRelationship.customLabel}</p>
          </div>
        )}
        {metadataEntries.length > 0 ? (
          <div>
            <p className="text-muted-foreground mb-1 text-xs">Metadata</p>
            <dl className="flex flex-col gap-1.5">
              {metadataEntries.map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">{key}</dt>
                  <dd className={cn(isSensitiveMetadataKey(key) && "font-mono")}>{maskMetadataValue(key, value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : (
          <p className="text-muted-foreground text-xs">
            {relationshipsQuery.isLoading ? "Loading additional metadata…" : "No additional metadata recorded for this relationship."}
          </p>
        )}
      </div>
    </Drawer>
  );
}
