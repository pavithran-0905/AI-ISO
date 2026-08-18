"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { Alert } from "@/components/feedback/alert";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { ExecutionLogViewer } from "@/features/automation/components/execution-log-viewer";
import { useAutomationJob } from "@/features/automation/hooks/use-jobs";
import { executionDurationMs, formatDurationMs } from "@/features/automation/lib/duration";
import { splitExecutionVariables } from "@/features/automation/lib/execution-variables";
import { EXECUTION_STATUS_TO_STATUS } from "@/features/automation/lib/status-maps";
import { ACTIVE_EXECUTION_STATUSES, type AutomationExecution } from "@/features/automation/types";

/**
 * Execution Detail (§9) — identity, lifecycle, timestamps, variables,
 * targets, and logs, all from real `AutomationExecutionResponse`
 * fields.
 *
 * No "Result"/"Output"/"Exit code" section: `AutomationResult` and
 * `AutomationOutput` rows are genuinely written backend-side but no
 * route exposes them, so the logs are the only reachable output. No
 * per-step breakdown either, for the same reason
 * (`AutomationExecutionStepResponse` exists, no route serves it). See
 * `docs/frontend/backend-v1-integration-limitations.md`.
 *
 * `errorMessage` is rendered as-is: it is the backend's own
 * user-facing message, never a stack trace (§35 — confirmed by
 * inspecting how `_finalize_execution` populates it).
 */
export function ExecutionDetailView({ execution }: { execution: AutomationExecution }) {
  const jobQuery = useAutomationJob(execution.jobId);
  const { variables, targetIds } = splitExecutionVariables(execution);
  const isActive = ACTIVE_EXECUTION_STATUSES.has(execution.status);
  const variableEntries = Object.entries(variables);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Status</p>
              <StatusIndicator state={EXECUTION_STATUS_TO_STATUS[execution.status]} />
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Automation</p>
              <p className="text-sm font-medium">
                {jobQuery.data ? (
                  <Link href={`/automation/automations/${execution.jobId}`} className="hover:underline">
                    {jobQuery.data.name}
                  </Link>
                ) : (
                  <span className="font-mono text-xs">{execution.jobId}</span>
                )}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Mode</p>
              <p className="text-sm font-medium">{execution.executionMode.replace(/_/g, " ")}</p>
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Duration</p>
              <p className="text-sm font-medium">{formatDurationMs(executionDurationMs(execution)) ?? "—"}</p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <Field label="Execution id" value={execution.id} mono />
            <Field label="Triggered by" value={execution.triggeredBy} mono />
            <Field label="Timeout" value={execution.timeoutSeconds ? `${execution.timeoutSeconds}s` : null} />
          </dl>
        </CardContent>
      </Card>

      {execution.errorMessage && (
        <Alert tone="danger" title="This run reported an error">
          {execution.errorMessage}
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Timestamps</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-6">
          <TimeField label="Created" value={execution.createdAt} />
          <TimeField label="Started" value={execution.startedAt} />
          <TimeField label="Completed" value={execution.completedAt} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Variables</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {variableEntries.length === 0 ? (
            <p className="text-muted-foreground text-sm">This run used no variables.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              {variableEntries.map(([key, value]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <dt className="text-muted-foreground font-mono text-xs">{key}</dt>
                  <dd className="font-mono text-xs">{String(value)}</dd>
                </div>
              ))}
            </dl>
          )}
          <p className="text-muted-foreground text-xs">
            These are the automation&rsquo;s own defaults merged with any values supplied for this run. AI-IOS stores them
            with the run for reference; it does not substitute them into the script content.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Targets</CardTitle>
        </CardHeader>
        <CardContent>
          {targetIds.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No targets — this run executed on the AI-IOS automation host.
            </p>
          ) : (
            <ul className="flex flex-col gap-1">
              {targetIds.map((targetId) => (
                <li key={targetId} className="font-mono text-xs">
                  {targetId}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Output</CardTitle>
        </CardHeader>
        <CardContent>
          <ExecutionLogViewer executionId={execution.id} isActive={isActive} />
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

function TimeField({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-sm font-medium">{value ? <time dateTime={value}>{new Date(value).toLocaleString()}</time> : "—"}</p>
    </div>
  );
}
