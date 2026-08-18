"use client";

import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useServiceTopology } from "@/features/monitoring/hooks/use-service-topology";
import { SERVICE_NODE_HEALTH_TO_STATUS } from "@/features/monitoring/lib/status-maps";
import type { ServiceHealthNode } from "@/features/monitoring/types";

/**
 * Service Health (§9) — `GET /observability/topology`'s per-service
 * `health`, derived from the platform's real dependency graph (not a
 * live probe, and not the same data as the Dashboard's
 * `GET /gateway/health` instance list — see the developer guide for
 * how the two relate).
 */
export function ServiceHealthList({ limit }: { limit?: number }) {
  const query = useServiceTopology();

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-48 w-full">
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No services in the topology yet" description="Nothing has been observed for this environment yet." />
        ) : (
          <ServiceList nodes={query.data} limit={limit} />
        ))}
    </SectionState>
  );
}

function ServiceList({ nodes, limit }: { nodes: ServiceHealthNode[]; limit?: number }) {
  const visible = limit ? nodes.slice(0, limit) : nodes;

  return (
    <ul className="divide-border border-border divide-y rounded-lg border">
      {visible.map((node) => (
        <li key={node.serviceName} className="flex items-center justify-between gap-3 p-3 text-sm">
          <span className="font-mono text-xs">{node.serviceName}</span>
          <span className="flex items-center gap-3">
            <span className="text-muted-foreground text-xs">
              {node.fanIn} in · {node.fanOut} out
            </span>
            <StatusIndicator state={SERVICE_NODE_HEALTH_TO_STATUS[node.health]} />
          </span>
        </li>
      ))}
    </ul>
  );
}
