"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { InfrastructureSubNav } from "@/features/infrastructure/components/infrastructure-sub-nav";
import { TopologyWorkspace } from "@/features/infrastructure/components/topology-workspace";
import { useSelectedOrganization } from "@/organization/use-organizations";

/**
 * Topology — `/infrastructure/topology` (§3). `focus`/`view` live in
 * the URL (§27) so a specific graph is bookmarkable/shareable; the
 * in-drawer node/edge selection does not (transient UI state, not
 * worth the URL noise §27 also warns against for large payloads).
 */
export function TopologyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();

  const focusAssetId = searchParams.get("focus");
  const view = searchParams.get("view") === "list" ? "list" : "graph";

  const updateParams = useCallback(
    (next: Partial<{ focus: string; view: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/infrastructure/topology?${params.toString()}`);
    },
    [router, searchParams],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Topology" description="Explore infrastructure relationships and dependencies, one asset at a time." />
      <InfrastructureSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <TopologyWorkspace
            organizationId={selectedOrganizationId}
            focusAssetId={focusAssetId}
            view={view}
            onFocusAsset={(assetId) => updateParams({ focus: assetId })}
            onViewChange={(nextView) => updateParams({ view: nextView === "graph" ? "" : nextView })}
          />
        )}
      </SectionState>
    </div>
  );
}
