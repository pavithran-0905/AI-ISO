"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ReportEditForm } from "@/features/reporting/components/report-edit-form";
import { useReport, useUpdateReport } from "@/features/reporting/hooks/use-reports";
import { toast } from "@/state/toast-store";

/** `/reporting/reports/[id]/edit`. */
export function ReportEditPage({ reportId }: { reportId: string }) {
  const router = useRouter();
  const query = useReport(reportId);
  const updateReport = useUpdateReport(reportId);

  async function handleSubmit(input: Parameters<typeof updateReport.mutateAsync>[0]) {
    try {
      await updateReport.mutateAsync(input);
      toast.success("Report updated");
      router.push(`/reporting/reports/${reportId}`);
    } catch {
      toast.danger("Failed to update report", "Please try again.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data ? `Edit ${query.data.name}` : "Edit report"}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push(`/reporting/reports/${reportId}`)}>
            Cancel
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
        {query.data && <ReportEditForm report={query.data} onSubmit={handleSubmit} isSubmitting={updateReport.isPending} />}
      </SectionState>
    </div>
  );
}
