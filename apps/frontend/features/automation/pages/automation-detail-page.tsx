"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { JobDetailView } from "@/features/automation/components/job-detail-view";
import { useAutomationJob } from "@/features/automation/hooks/use-jobs";

/** Automation Detail (§6) — `/automation/automations/[id]`. */
export function AutomationDetailPage({ jobId }: { jobId: string }) {
  const router = useRouter();
  const query = useAutomationJob(jobId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.name ?? "Automation"}
        description={query.data ? query.data.automationType.replace(/_/g, " ") : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/automation/automations")}>
            Back to Automations
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
        {query.data && <JobDetailView job={query.data} />}
      </SectionState>
    </div>
  );
}
