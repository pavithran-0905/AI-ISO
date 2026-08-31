"use client";

import { RefreshCw, Server } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { ResourceBreadcrumbs } from "@/components/resource/resource-breadcrumbs";
import { ResourceHeader } from "@/components/resource/resource-header";
import { ResourceNotFound } from "@/components/resource/resource-not-found";
import { StatusBadge } from "@/components/feedback/status-badge";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { IconButton } from "@/components/ui/icon-button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AssetDetailView } from "@/features/infrastructure/components/asset-detail-view";
import { useAsset } from "@/features/infrastructure/hooks/use-assets";
import { ASSET_HEALTH_TO_STATUS, ASSET_STATUS_TONE } from "@/features/infrastructure/lib/status-maps";
import { getRouteById } from "@/lib/route-registry";

const INFRASTRUCTURE_ROUTE = getRouteById("infrastructure");
const ASSETS_ROUTE = getRouteById("infrastructure-assets");

/**
 * Asset Detail — `/infrastructure/assets/[id]`. The reference
 * implementation of Prompt 018's reusable resource-workspace
 * primitives (`components/resource/*`) — see
 * `docs/frontend/developer-guide/resource-investigation.md` for why
 * Infrastructure Assets is the only resource type this session
 * retrofits onto them, and why "Machine"/"VM"/"Service"/"Application"
 * are `assetType` values of one real backend model, not separate
 * resources needing separate adapters.
 */
export function AssetDetailPage({ assetId }: { assetId: string }) {
  const queryClient = useQueryClient();
  const query = useAsset(assetId);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const notFound = query.error instanceof ApiRequestError && query.error.status === 404;

  async function refresh() {
    setIsRefreshing(true);
    // Scoped to this resource's own real query keys (§21: "refresh
    // only the necessary resource data") — never a whole-application
    // invalidation.
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "assets", assetId] }),
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "relationships", assetId] }),
      queryClient.invalidateQueries({ queryKey: ["infrastructure", "topology", assetId] }),
    ]);
    setIsRefreshing(false);
  }

  if (notFound) {
    return (
      <div className="flex flex-col gap-6">
        <ResourceBreadcrumbs
          trail={[
            ...(INFRASTRUCTURE_ROUTE ? [{ label: INFRASTRUCTURE_ROUTE.breadcrumb, href: INFRASTRUCTURE_ROUTE.path }] : []),
            ...(ASSETS_ROUTE ? [{ label: ASSETS_ROUTE.breadcrumb, href: ASSETS_ROUTE.path }] : []),
            { label: "Not found" },
          ]}
        />
        <ResourceNotFound resourceLabel="Asset" backHref="/infrastructure/assets" backLabel="Back to Assets" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <ResourceBreadcrumbs
        trail={[
          ...(INFRASTRUCTURE_ROUTE ? [{ label: INFRASTRUCTURE_ROUTE.breadcrumb, href: INFRASTRUCTURE_ROUTE.path }] : []),
          ...(ASSETS_ROUTE ? [{ label: ASSETS_ROUTE.breadcrumb, href: ASSETS_ROUTE.path }] : []),
          { label: query.data?.displayName ?? query.data?.name ?? "Asset" },
        ]}
      />

      <ResourceHeader
        icon={Server}
        title={query.data?.displayName ?? query.data?.name ?? "Asset"}
        resourceType={query.data?.assetType}
        statusBadges={
          query.data && (
            <>
              <StatusIndicator state={ASSET_HEALTH_TO_STATUS[query.data.health]} />
              <StatusBadge tone={ASSET_STATUS_TONE[query.data.status]} label={query.data.status} />
            </>
          )
        }
        identifier={query.data?.hostname ?? undefined}
        environment={query.data?.environment}
        lastUpdatedAt={query.data?.updatedAt}
        secondaryActions={
          <IconButton icon={RefreshCw} aria-label="Refresh asset data" variant="outline" loading={isRefreshing} onClick={() => void refresh()} />
        }
      />

      <SectionState isLoading={query.isLoading} isError={query.isError && !notFound} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
        {query.data && <AssetDetailView asset={query.data} />}
      </SectionState>
    </div>
  );
}
