"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { JobForm, type JobFormValues } from "@/features/automation/components/job-form";
import { useAutomationJob, useUpdateAutomationJob } from "@/features/automation/hooks/use-jobs";
import type { AutomationJob } from "@/features/automation/types";
import { toast } from "@/state/toast-store";

/** `/automation/automations/[id]/edit`. */
export function AutomationEditPage({ jobId }: { jobId: string }) {
  const router = useRouter();
  const query = useAutomationJob(jobId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data ? `Edit ${query.data.name}` : "Edit automation"}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push(`/automation/automations/${jobId}`)}>
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
        {query.data && <EditForm job={query.data} />}
      </SectionState>
    </div>
  );
}

/** Split out so the form's local state is seeded once from real
 * loaded data rather than synced in via an effect. */
function EditForm({ job }: { job: AutomationJob }) {
  const router = useRouter();
  const updateJob = useUpdateAutomationJob(job.id);

  async function handleSubmit(values: JobFormValues) {
    try {
      // Every field is sent, including `status` — `PUT /automation/jobs/{id}`
      // is a full replace whose schema defaults `status` to `draft`, so
      // omitting it would silently demote a live automation.
      await updateJob.mutateAsync({
        name: values.name,
        description: values.description || null,
        status: values.status,
        automationType: values.automationType,
        playbookType: values.playbookType,
        executionMode: values.executionMode,
        content: values.content,
        targetSelector: job.targetSelector,
        variables: values.variables,
        tags: values.tags,
        timeoutSeconds: values.timeoutSeconds,
        ownerId: job.ownerId,
      });
      toast.success("Automation updated");
      router.push(`/automation/automations/${job.id}`);
    } catch {
      toast.danger("Could not update this automation", "Please try again.");
    }
  }

  return <JobForm job={job} onSubmit={handleSubmit} isSubmitting={updateJob.isPending} submitLabel="Save changes" />;
}
