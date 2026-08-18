"use client";

import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { Alert } from "@/components/feedback/alert";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ExecutionTable, type ExecutionSortField } from "@/features/automation/components/execution-table";
import { JobActions } from "@/features/automation/components/job-actions";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import { JOB_STATUS_TONE } from "@/features/automation/lib/status-maps";
import { RUNNABLE_PLAYBOOK_TYPES, type AutomationJob } from "@/features/automation/types";

const RECENT_LIMIT = 10;
const SORT_FIELD: ExecutionSortField = "createdAt";

/**
 * Automation Detail (§6) — identity, configuration, actions, and this
 * automation's own recent runs.
 *
 * The run history is filtered client-side from the organization-wide
 * execution list: there is no `GET /automation/jobs/{id}/executions`
 * endpoint (the service method exists but no route calls it). Since
 * the org list is returned complete and unpaginated, filtering it here
 * still shows every run of this job — nothing is hidden — but it does
 * mean fetching more than strictly needed. Documented in
 * `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function JobDetailView({ job }: { job: AutomationJob }) {
  const executionsQuery = useExecutions({ organizationId: job.organizationId });

  const jobExecutions = useMemo(
    () =>
      (executionsQuery.data ?? [])
        .filter((execution) => execution.jobId === job.id)
        .slice(0, RECENT_LIMIT),
    [executionsQuery.data, job.id],
  );
  const jobNameById = useMemo(() => new Map([[job.id, job.name]]), [job.id, job.name]);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">Status</dt>
              <dd>
                <StatusBadge tone={JOB_STATUS_TONE[job.status]} label={job.status} />
              </dd>
            </div>
            <Field label="Type" value={job.automationType.replace(/_/g, " ")} />
            <Field label="Playbook" value={job.playbookType.replace(/_/g, " ")} />
            <Field label="Execution mode" value={job.executionMode.replace(/_/g, " ")} />
            <Field label="Timeout" value={job.timeoutSeconds ? `${job.timeoutSeconds}s` : null} />
            <Field label="Owner id" value={job.ownerId} mono />
          </dl>
          {job.description && <p className="text-muted-foreground text-sm">{job.description}</p>}
          {job.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {job.tags.map((tag) => (
                <Badge key={tag} variant="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {!RUNNABLE_PLAYBOOK_TYPES.has(job.playbookType) && (
        <Alert tone="warning" title="This playbook type can't be executed yet">
          AI-IOS can currently run shell, bash, Python, PowerShell, and Ansible content. Running this automation will
          fail when it reaches the dispatcher.
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <JobActions job={job} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Content</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="bg-muted overflow-x-auto rounded-md p-3 text-xs whitespace-pre-wrap">{job.content}</pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Default variables</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {Object.keys(job.variables).length === 0 ? (
            <p className="text-muted-foreground text-sm">No default variables.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              {Object.entries(job.variables).map(([key, value]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <dt className="text-muted-foreground font-mono text-xs">{key}</dt>
                  <dd className="font-mono text-xs">{String(value)}</dd>
                </div>
              ))}
            </dl>
          )}
          <p className="text-muted-foreground text-xs">
            Merged into every run&rsquo;s own variables and stored with it. AI-IOS does not substitute these into the
            script content.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent>
          <SectionState
            isLoading={executionsQuery.isLoading}
            isError={executionsQuery.isError}
            error={executionsQuery.error}
            onRetry={() => executionsQuery.refetch()}
          >
            {executionsQuery.data &&
              (jobExecutions.length === 0 ? (
                <EmptyState title="No executions found" description="This automation hasn't been run yet." />
              ) : (
                <ExecutionTable
                  executions={jobExecutions}
                  jobNameById={jobNameById}
                  sortField={SORT_FIELD}
                  sortDirection="desc"
                  onSortChange={() => undefined}
                />
              ))}
          </SectionState>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : "text-sm"}>{value}</dd>
    </div>
  );
}
