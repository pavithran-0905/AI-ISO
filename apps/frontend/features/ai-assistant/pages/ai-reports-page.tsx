"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { AiReportForm } from "@/features/ai-assistant/components/ai-report-form";
import { AiReportList } from "@/features/ai-assistant/components/ai-report-list";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { usePermissions } from "@/permissions/hooks";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/intelligence/reports` — a genuinely distinct resource from
 * `reporting-service`'s own reports (§26: "do not create a duplicate
 * reporting architecture"); see `AiReport`'s own docstring. */
export function AiReportsPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { can } = usePermissions();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="AI Reports" description="Narrative reports written by the assistant, distinct from reporting-service's own reports." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-6">
            {can("create") && <AiReportForm organizationId={selectedOrganizationId} />}
            <AiReportList organizationId={selectedOrganizationId} />
          </div>
        )}
      </SectionState>
    </div>
  );
}
