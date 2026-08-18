"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { RecommendationForm } from "@/features/ai-assistant/components/recommendation-form";
import { RecommendationList } from "@/features/ai-assistant/components/recommendation-list";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { usePermissions } from "@/permissions/hooks";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/intelligence/recommendations`. */
export function RecommendationsPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { can } = usePermissions();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Recommendations" description="AI-generated recommendations awaiting or already given a decision." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-6">
            {can("create") && <RecommendationForm organizationId={selectedOrganizationId} />}
            <RecommendationList organizationId={selectedOrganizationId} />
          </div>
        )}
      </SectionState>
    </div>
  );
}
