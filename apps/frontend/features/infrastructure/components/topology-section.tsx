"use client";

import Link from "next/link";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
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

/**
 * `GET /inventory/topology` (§15) — a real, structured list, not a
 * graph: topology data exists, but §53 forbids adding a graph library
 * for one view, and §15 explicitly defers graph visualization to a
 * future feature when this is the case. Three real query kinds, each
 * a distinct traversal the backend actually computes (neighbors:
 * direct edges; dependencies: what this asset depends on, transitively;
 * impact: what would be affected if this asset failed).
 */
export function TopologySection({ assetId }: { assetId: string }) {
  const [kind, setKind] = useState<TopologyQueryKindValue>("neighbors");
  const query = useTopology(assetId, kind, kind === "neighbors" ? undefined : 2);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Topology</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="border-border flex gap-1 border-b" role="tablist" aria-label="Topology view">
          {TOPOLOGY_QUERY_KINDS.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={kind === value}
              onClick={() => setKind(value)}
              className={cn(
                "border-b-2 px-2 py-1.5 text-xs font-medium transition-colors",
                "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                kind === value ? "border-primary text-foreground" : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              {KIND_LABEL[value]}
            </button>
          ))}
        </div>

        <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
          {query.data &&
            (query.data.nodes.length === 0 ? (
              <EmptyState title="No relationships available" description={`No ${KIND_LABEL[kind].toLowerCase()} found for this asset.`} />
            ) : (
              <ul className="flex flex-col gap-1.5">
                {query.data.nodes.map((node) => (
                  <li key={node.id} className="flex items-center justify-between gap-3 text-sm">
                    <Link href={`/infrastructure/assets/${node.id}`} className="font-medium hover:underline">
                      {node.name}
                    </Link>
                    <span className="text-muted-foreground text-xs">
                      {node.assetType}
                      {node.distance !== null ? ` · ${node.distance} hop${node.distance === 1 ? "" : "s"}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>
    </Card>
  );
}
