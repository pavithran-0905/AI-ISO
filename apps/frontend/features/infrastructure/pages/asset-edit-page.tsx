"use client";

import { useRouter } from "next/navigation";

import { ApiRequestError } from "@/api/client";
import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AssetEditForm } from "@/features/infrastructure/components/asset-edit-form";
import { useAsset, usePatchAsset } from "@/features/infrastructure/hooks/use-assets";
import { toast } from "@/state/toast-store";

/** `/infrastructure/assets/[id]/edit`. */
export function AssetEditPage({ assetId }: { assetId: string }) {
  const router = useRouter();
  const query = useAsset(assetId);
  const patchAsset = usePatchAsset(assetId);

  async function handleSubmit(input: Parameters<typeof patchAsset.mutateAsync>[0]) {
    try {
      await patchAsset.mutateAsync(input);
      toast.success("Asset updated");
      router.push(`/infrastructure/assets/${assetId}`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please check the form and try again.";
      toast.danger("Could not update asset", message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data ? `Edit ${query.data.displayName ?? query.data.name}` : "Edit asset"}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push(`/infrastructure/assets/${assetId}`)}>
            Back to Asset
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
        {query.data && <AssetEditForm asset={query.data} onSubmit={handleSubmit} isSubmitting={patchAsset.isPending} />}
      </SectionState>
    </div>
  );
}
