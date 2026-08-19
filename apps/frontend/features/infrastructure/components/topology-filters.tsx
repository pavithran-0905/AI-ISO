"use client";

import { useMemo } from "react";

import { Checkbox } from "@/components/forms/checkbox";
import type { TopologyGraph } from "@/features/infrastructure/types";

/**
 * §15: `GET /inventory/topology` accepts no filter parameters at all
 * (confirmed absent by source inspection) — this is a client-side
 * *display* toggle over the already-loaded, single-root/1-hop response
 * only, never a re-query, and clearly scoped to the asset types
 * actually present in the current graph rather than the full 44-value
 * `ASSET_TYPES` vocabulary.
 */
export function TopologyFilters({
  graph,
  visibleAssetTypes,
  onChange,
}: {
  graph: TopologyGraph;
  visibleAssetTypes: ReadonlySet<string> | null;
  onChange: (next: ReadonlySet<string> | null) => void;
}) {
  const presentTypes = useMemo(
    () => Array.from(new Set(graph.nodes.filter((node) => !node.isRoot).map((node) => node.assetType))).sort(),
    [graph.nodes],
  );

  if (presentTypes.length === 0) return null;

  function toggle(type: string) {
    const current = visibleAssetTypes ?? new Set(presentTypes);
    const next = new Set(current);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    onChange(next.size === presentTypes.length ? null : next);
  }

  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="text-muted-foreground mb-1 text-xs font-medium">Show relationship types</legend>
      {presentTypes.map((type) => {
        const checked = visibleAssetTypes ? visibleAssetTypes.has(type) : true;
        return (
          <label key={type} className="flex items-center gap-2 text-xs">
            <Checkbox checked={checked} onChange={() => toggle(type)} />
            {type}
          </label>
        );
      })}
    </fieldset>
  );
}
