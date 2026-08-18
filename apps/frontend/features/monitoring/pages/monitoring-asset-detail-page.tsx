"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AssetDetailView } from "@/features/monitoring/components/asset-detail-view";
import { useAsset } from "@/features/monitoring/hooks/use-asset";

/**
 * Asset Detail (§8) — `/monitoring/assets/[id]`. Not registered in
 * `lib/route-registry.ts` (dynamic id, no static breadcrumb entry
 * possible with the current flat registry) — the page renders its own
 * "Back to Assets" action instead.
 */
export function MonitoringAssetDetailPage({ assetId }: { assetId: string }) {
  const router = useRouter();
  const query = useAsset(assetId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.displayName ?? query.data?.name ?? "Asset"}
        description={query.data ? `${query.data.assetType} · ${query.data.environment ?? "no environment"}` : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/monitoring/assets")}>
            Back to Assets
          </Button>
        }
      />

      <SectionState
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => query.refetch()}
        skeletonClassName="h-96 w-full"
      >
        {query.data && <AssetDetailView asset={query.data} />}
      </SectionState>
    </div>
  );
}
