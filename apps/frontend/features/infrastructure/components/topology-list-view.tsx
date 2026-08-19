"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useTopology } from "@/features/infrastructure/hooks/use-topology";
import { TOPOLOGY_QUERY_KINDS, type TopologyQueryKindValue } from "@/features/infrastructure/types";
import { cn } from "@/utils/cn";

const KIND_LABEL: Record<TopologyQueryKindValue, string> = {
  neighbors: "Neighbors",
  dependencies: "Dependencies",
  impact: "Impact",
};

const DEPTHS = [1, 2, 3, 4, 5] as const;

/**
 * §43/§44: the accessible, screen-reader-friendly structured
 * alternative to the graph canvas — required, not optional, since a
 * graph is difficult for assistive technology. Also the *only* honest
 * way to show `dependencies`/`impact` at all: those two query kinds
 * return a flat, distance-tagged node list with no parent linkage
 * (confirmed by source inspection — see `TopologyGraph`'s own
 * docstring), so they were never going to be canvas-renderable as real
 * multi-hop edges. Depth (§16) is real here — `GET /inventory/topology`
 * accepts `depth=1..5` for these two kinds specifically; `neighbors`
 * ignores it (the backend route never passes it through), so the
 * control is hidden for that tab rather than shown and silently
 * ignored.
 */
export function TopologyListView({ assetId, onFocusAsset }: { assetId: string; onFocusAsset: (assetId: string) => void }) {
  const [kind, setKind] = useState<TopologyQueryKindValue>("neighbors");
  const [depth, setDepth] = useState(2);
  const query = useTopology(assetId, kind, kind === "neighbors" ? undefined : depth);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="border-border flex gap-1 border-b" role="tablist" aria-label="Topology view">
          {TOPOLOGY_QUERY_KINDS.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={kind === value}
              onClick={() => setKind(value)}
              className={cn(
                "border-b-2 px-3 py-1.5 text-sm font-medium transition-colors",
                "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                kind === value ? "border-primary text-foreground" : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              {KIND_LABEL[value]}
            </button>
          ))}
        </div>

        {kind !== "neighbors" && (
          <div className="flex items-center gap-2">
            <Label htmlFor="topology-depth" className="text-xs">
              Depth
            </Label>
            <Select id="topology-depth" value={String(depth)} onChange={(event) => setDepth(Number(event.target.value))} className="w-20">
              {DEPTHS.map((value) => (
                <option key={value} value={value}>
                  {value} hop{value === 1 ? "" : "s"}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>

      {kind === "neighbors" && (
        <p className="text-muted-foreground text-xs">Direct connections only — depth doesn&apos;t apply to this view.</p>
      )}

      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
        {query.data &&
          (query.data.nodes.length === 0 ? (
            <EmptyState title="No relationships found" description={`No ${KIND_LABEL[kind].toLowerCase()} found for this asset.`} />
          ) : (
            <ul className="flex flex-col gap-1.5">
              {query.data.nodes.map((node) => (
                <li key={node.id} className="border-border flex items-center justify-between gap-3 border-b py-2 text-sm last:border-0">
                  <div className="flex flex-col gap-0.5">
                    <Link href={`/infrastructure/assets/${node.id}`} className="font-medium hover:underline">
                      {node.name}
                    </Link>
                    <span className="text-muted-foreground text-xs">
                      {node.assetType}
                      {node.relationshipType ? ` · ${node.outgoing === false ? `${node.relationshipType} (incoming)` : node.relationshipType}` : ""}
                      {node.distance !== null ? ` · ${node.distance} hop${node.distance === 1 ? "" : "s"}` : ""}
                    </span>
                  </div>
                  <Button variant="outline" onClick={() => onFocusAsset(node.id)}>
                    Focus
                  </Button>
                </li>
              ))}
            </ul>
          ))}
      </SectionState>
    </div>
  );
}
