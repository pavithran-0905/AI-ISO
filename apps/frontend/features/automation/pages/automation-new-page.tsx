"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { JobForm, type JobFormValues } from "@/features/automation/components/job-form";
import { useCreateAutomationJob } from "@/features/automation/hooks/use-jobs";
import { toast } from "@/state/toast-store";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/automation/automations/new`. The backend hard-codes a new job's
 * status to `active`, so the form doesn't offer that control here. */
export function AutomationNewPage() {
  const router = useRouter();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const createJob = useCreateAutomationJob();

  async function handleSubmit(values: JobFormValues) {
    if (!selectedOrganizationId) return;
    try {
      const job = await createJob.mutateAsync({
        organizationId: selectedOrganizationId,
        name: values.name,
        description: values.description || undefined,
        automationType: values.automationType,
        playbookType: values.playbookType,
        executionMode: values.executionMode,
        content: values.content,
        variables: values.variables,
        tags: values.tags,
        timeoutSeconds: values.timeoutSeconds,
      });
      toast.success("Automation created");
      router.push(`/automation/automations/${job.id}`);
    } catch {
      toast.danger("Could not create this automation", "Please check the form and try again.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="New automation"
        description="Define an automation job for this organization."
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/automation/automations")}>
            Back to Automations
          </Button>
        }
      />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && <JobForm onSubmit={handleSubmit} isSubmitting={createJob.isPending} submitLabel="Create automation" />}
      </SectionState>
    </div>
  );
}
