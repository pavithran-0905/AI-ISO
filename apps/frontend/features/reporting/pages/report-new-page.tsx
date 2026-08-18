"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ReportForm } from "@/features/reporting/components/report-form";
import { useCreateReport } from "@/features/reporting/hooks/use-reports";
import { toast } from "@/state/toast-store";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/reporting/reports/new`. */
export function ReportNewPage() {
  const router = useRouter();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const createReport = useCreateReport();

  async function handleSubmit(input: Parameters<typeof createReport.mutateAsync>[0]) {
    try {
      const report = await createReport.mutateAsync(input);
      toast.success("Report created");
      router.push(`/reporting/reports/${report.id}`);
    } catch {
      toast.danger("Failed to create report", "Please check the form and try again.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="New report"
        description="Save a report configuration for this organization."
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/reporting/reports")}>
            Back to Reports
          </Button>
        }
      />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <ReportForm organizationId={selectedOrganizationId} onSubmit={handleSubmit} isSubmitting={createReport.isPending} />
        )}
      </SectionState>
    </div>
  );
}
