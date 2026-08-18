"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ReportDetailView } from "@/features/reporting/components/report-detail-view";
import { useReport } from "@/features/reporting/hooks/use-reports";

/**
 * Report Detail — `/reporting/reports/[id]`. Not registered in
 * `lib/route-registry.ts` (dynamic id, mirrors `MonitoringAssetDetailPage`'s
 * own reasoning) — renders its own "Back to Reports" action instead.
 */
export function ReportDetailPage({ reportId }: { reportId: string }) {
  const router = useRouter();
  const query = useReport(reportId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.name ?? "Report"}
        description={query.data ? `${query.data.category} · ${query.data.reportType}` : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/reporting/reports")}>
            Back to Reports
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
        {query.data && <ReportDetailView organizationId={query.data.organizationId} report={query.data} />}
      </SectionState>
    </div>
  );
}
