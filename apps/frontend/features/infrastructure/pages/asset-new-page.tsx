"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AssetCreateForm } from "@/features/infrastructure/components/asset-create-form";
import { useCreateAsset } from "@/features/infrastructure/hooks/use-assets";
import { toast } from "@/state/toast-store";
import { ApiRequestError } from "@/api/client";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/infrastructure/assets/new`. */
export function AssetNewPage() {
  const router = useRouter();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const createAsset = useCreateAsset();

  async function handleSubmit(input: Parameters<typeof createAsset.mutateAsync>[0]) {
    try {
      const asset = await createAsset.mutateAsync(input);
      toast.success("Asset registered");
      router.push(`/infrastructure/assets/${asset.id}`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please check the form and try again.";
      toast.danger("Could not register asset", message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="New asset"
        description="Register an asset for this organization."
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/infrastructure/assets")}>
            Back to Assets
          </Button>
        }
      />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <AssetCreateForm organizationId={selectedOrganizationId} onSubmit={handleSubmit} isSubmitting={createAsset.isPending} />
        )}
      </SectionState>
    </div>
  );
}
