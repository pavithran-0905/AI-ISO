"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ExecutionDetailView } from "@/features/automation/components/execution-detail-view";
import { useExecution } from "@/features/automation/hooks/use-executions";

/** Execution Detail (§9) — `/automation/executions/[id]`. Not
 * registered in `lib/route-registry.ts` (dynamic id) — renders its own
 * "Back to Executions" action instead. Polls itself while the run is
 * still in flight. */
export function ExecutionDetailPage({ executionId }: { executionId: string }) {
  const router = useRouter();
  const query = useExecution(executionId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data ? `Run ${query.data.id.slice(0, 8)}` : "Execution"}
        description={query.data ? query.data.status.replace(/_/g, " ") : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/automation/executions")}>
            Back to Executions
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
        {query.data && <ExecutionDetailView execution={query.data} />}
      </SectionState>
    </div>
  );
}
