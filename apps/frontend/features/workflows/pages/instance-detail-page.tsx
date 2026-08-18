"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { InstanceDetailView } from "@/features/workflows/components/instance-detail-view";
import { useWorkflowInstance } from "@/features/workflows/hooks/use-workflows";

/** `/workflows/instances/[id]`. Polls itself while the instance is
 * still in flight. */
export function InstanceDetailPage({ instanceId }: { instanceId: string }) {
  const router = useRouter();
  const query = useWorkflowInstance(instanceId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data ? `Run ${query.data.id.slice(0, 8)}` : "Workflow instance"}
        description={query.data ? query.data.status.replace(/_/g, " ") : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/workflows/instances")}>
            Back to Instances
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
        {query.data && <InstanceDetailView instance={query.data} />}
      </SectionState>
    </div>
  );
}
