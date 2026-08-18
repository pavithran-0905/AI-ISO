"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { AiStatisticsSummary } from "@/features/ai-assistant/components/ai-statistics-summary";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/intelligence/analytics`. */
export function AnalyticsPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Analytics" description="Usage, cost, latency, and feedback statistics for the assistant." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && <AiStatisticsSummary organizationId={selectedOrganizationId} />}
      </SectionState>
    </div>
  );
}
