"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Dialog } from "@/components/overlays/dialog";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useEnqueueSystemJob, useSystemJobs } from "@/features/settings/hooks/use-system-settings";
import { toast } from "@/state/toast-store";

/** `GET/POST /admin/jobs` — enqueue + read-only list only; no route
 * cancels, retries, or transitions a job after enqueue (confirmed
 * absent). Same roles-claim permission gap as the other System
 * mutations. */
export function SystemJobsSection() {
  const jobsQuery = useSystemJobs();
  const enqueueJob = useEnqueueSystemJob();
  const [open, setOpen] = useState(false);
  const [jobKey, setJobKey] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await enqueueJob.mutateAsync({ jobKey });
      toast.success("Job enqueued");
      setOpen(false);
      setJobKey("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not enqueue job", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Background jobs</CardTitle>
          <CardDescription>Enqueue and view — no cancel/retry route exists on this backend.</CardDescription>
        </div>
        <IconButton icon={Plus} aria-label="Enqueue job" variant="outline" onClick={() => setOpen(true)} />
      </CardHeader>
      <CardContent>
        <SectionState isLoading={jobsQuery.isLoading} isError={jobsQuery.isError} error={jobsQuery.error} onRetry={() => jobsQuery.refetch()}>
          {jobsQuery.data &&
            (jobsQuery.data.length === 0 ? (
              <EmptyState title="No jobs queued" description="Enqueue one below." />
            ) : (
              <ul className="flex flex-col gap-2">
                {jobsQuery.data.map((job) => (
                  <li key={job.id} className="flex items-center justify-between gap-3 text-sm">
                    <p className="font-mono">{job.jobKey}</p>
                    <span className="text-muted-foreground text-xs">
                      {job.status} · attempt {job.attemptCount}/{job.maxAttempts}
                    </span>
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>

      <Dialog open={open} onClose={() => setOpen(false)} title="Enqueue a job">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <FormField label="Job key" required>
            {(fieldProps) => <Input {...fieldProps} value={jobKey} onChange={(event) => setJobKey(event.target.value)} required />}
          </FormField>
          <Button type="submit" loading={enqueueJob.isPending} disabled={!jobKey} className="w-fit">
            Enqueue
          </Button>
        </form>
      </Dialog>
    </Card>
  );
}
