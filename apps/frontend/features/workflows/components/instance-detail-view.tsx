"use client";

import Link from "next/link";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { StatusBadge } from "@/components/feedback/status-badge";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Textarea } from "@/components/forms/textarea";
import { SectionState } from "@/features/dashboard/components/section-state";
import { formatDurationMs } from "@/features/automation/lib/duration";
import {
  useDecideApproval,
  useInstanceApprovals,
  useInstanceLogs,
  useInstanceSteps,
  useWorkflow,
} from "@/features/workflows/hooks/use-workflows";
import { INSTANCE_STATUS_TO_STATUS, NODE_STATUS_TO_STATUS } from "@/features/workflows/lib/status-maps";
import { ACTIVE_INSTANCE_STATUSES, type WorkflowApproval, type WorkflowInstance } from "@/features/workflows/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Workflow Instance Detail — the per-node breakdown, logs, and
 * approval gates that make this service genuinely richer than
 * `automation-service` (whose own step rows exist but have no route).
 *
 * Variables aren't shown: `WorkflowExecuteRequest`'s `variables` go
 * into the queue message rather than onto the instance row, so they
 * are not readable back from any endpoint. Showing an empty or
 * reconstructed "Variables" section would be a fabrication.
 */
export function InstanceDetailView({ instance }: { instance: WorkflowInstance }) {
  const isActive = ACTIVE_INSTANCE_STATUSES.has(instance.status);
  const workflowQuery = useWorkflow(instance.definitionId);
  const stepsQuery = useInstanceSteps(instance.id, isActive);
  const logsQuery = useInstanceLogs(instance.id, isActive);
  const approvalsQuery = useInstanceApprovals(instance.id, isActive);

  const durationMs =
    instance.startedAt && instance.finishedAt
      ? new Date(instance.finishedAt).getTime() - new Date(instance.startedAt).getTime()
      : null;

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
              <StatusIndicator state={INSTANCE_STATUS_TO_STATUS[instance.status]} />
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Workflow</p>
              <p className="text-sm font-medium">
                {workflowQuery.data ? (
                  <Link href={`/workflows/${instance.definitionId}`} className="hover:underline">
                    {workflowQuery.data.name}
                  </Link>
                ) : (
                  <span className="font-mono text-xs">{instance.definitionId}</span>
                )}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Trigger</p>
              <p className="text-sm font-medium">{instance.triggerType}</p>
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Duration</p>
              <p className="text-sm font-medium">{formatDurationMs(durationMs) ?? "—"}</p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <Field label="Instance id" value={instance.id} mono />
            <Field label="Triggered by" value={instance.triggeredBy} mono />
            <Field label="Parent instance" value={instance.parentInstanceId} mono />
            <TimeField label="Started" value={instance.startedAt} />
            <TimeField label="Finished" value={instance.finishedAt} />
          </dl>
        </CardContent>
      </Card>

      {instance.errorMessage && (
        <Alert tone="danger" title="This run reported an error">
          {instance.errorMessage}
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Approvals</CardTitle>
        </CardHeader>
        <CardContent>
          <SectionState
            isLoading={approvalsQuery.isLoading}
            isError={approvalsQuery.isError}
            error={approvalsQuery.error}
            onRetry={() => approvalsQuery.refetch()}
          >
            {approvalsQuery.data &&
              (approvalsQuery.data.length === 0 ? (
                <EmptyState title="No approval gates" description="This workflow doesn't require human approval." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {approvalsQuery.data.map((approval) => (
                    <li key={approval.id}>
                      <ApprovalRow approval={approval} instanceId={instance.id} />
                    </li>
                  ))}
                </ul>
              ))}
          </SectionState>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Steps</CardTitle>
        </CardHeader>
        <CardContent>
          <SectionState
            isLoading={stepsQuery.isLoading}
            isError={stepsQuery.isError}
            error={stepsQuery.error}
            onRetry={() => stepsQuery.refetch()}
          >
            {stepsQuery.data &&
              (stepsQuery.data.length === 0 ? (
                <EmptyState title="No steps recorded" description="This run hasn't executed any nodes yet." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {stepsQuery.data.map((step) => (
                    <li key={step.id}>
                      <div className="border-border flex flex-col gap-2 rounded-md border p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-col gap-0.5">
                            <p className="text-sm font-medium">{step.nodeId}</p>
                            <p className="text-muted-foreground text-xs">
                              {step.nodeType}
                              {step.attempts > 1 && ` · ${step.attempts} attempts`}
                            </p>
                          </div>
                          <StatusIndicator state={NODE_STATUS_TO_STATUS[step.status]} />
                        </div>
                        {step.error && <p className="text-danger text-xs">{step.error}</p>}
                        {step.output && Object.keys(step.output).length > 0 && (
                          <pre className="bg-muted overflow-x-auto rounded p-2 text-xs whitespace-pre-wrap">
                            {JSON.stringify(step.output, null, 2)}
                          </pre>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              ))}
          </SectionState>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <SectionState
            isLoading={logsQuery.isLoading}
            isError={logsQuery.isError}
            error={logsQuery.error}
            onRetry={() => logsQuery.refetch()}
          >
            {logsQuery.data &&
              (logsQuery.data.length === 0 ? (
                <EmptyState title="No execution logs available" description="This run hasn't recorded any output." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {logsQuery.data.map((log) => (
                    <li key={log.id} className="border-border flex flex-col gap-1 rounded-md border p-3">
                      <div className="flex items-center gap-2">
                        <StatusBadge tone={log.level === "error" ? "danger" : log.level === "warning" ? "warning" : "info"} label={log.level} />
                        {log.nodeId && <span className="text-muted-foreground font-mono text-xs">{log.nodeId}</span>}
                        <time dateTime={log.loggedAt} className="text-muted-foreground text-xs">
                          {new Date(log.loggedAt).toLocaleString()}
                        </time>
                      </div>
                      <pre className="overflow-x-auto text-xs whitespace-pre-wrap">{log.message}</pre>
                    </li>
                  ))}
                </ul>
              ))}
          </SectionState>
          {isActive && <p className="text-muted-foreground mt-2 text-xs">Following this run — output refreshes automatically.</p>}
        </CardContent>
      </Card>
    </div>
  );
}

/** A real approval gate. The `approver` is typed in rather than taken
 * from the session because the backend models approvers as free-text
 * strings, not user ids — there is no reliable way to match the signed-in
 * user to an entry in `approvers`. */
function ApprovalRow({ approval, instanceId }: { approval: WorkflowApproval; instanceId: string }) {
  const { can } = usePermissions();
  const [approver, setApprover] = useState("");
  const [comments, setComments] = useState("");
  const decide = useDecideApproval(instanceId);

  async function handleDecide(approve: boolean) {
    if (!approver.trim()) {
      toast.danger("Who is approving?", "Enter the approver name recorded for this gate.");
      return;
    }
    try {
      await decide.mutateAsync({ approvalId: approval.id, input: { approver: approver.trim(), approve, comments: comments.trim() || undefined } });
      toast.success(approve ? "Approved" : "Rejected");
    } catch {
      toast.danger("Could not record that decision", "Please try again.");
    }
  }

  const isPending = approval.decision === "pending";

  return (
    <div className="border-border flex flex-col gap-3 rounded-md border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">{approval.nodeId}</p>
          <p className="text-muted-foreground text-xs">
            {approval.approvers.length > 0 ? approval.approvers.join(", ") : "No named approvers"} ·{" "}
            {approval.requiredApprovals} required
          </p>
        </div>
        <StatusBadge
          tone={approval.decision === "approved" ? "success" : approval.decision === "rejected" ? "danger" : approval.decision === "pending" ? "pending" : "neutral"}
          label={approval.decision}
        />
      </div>
      {approval.comments && <p className="text-muted-foreground text-sm">{approval.comments}</p>}

      {isPending && can("approve") && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`approver-${approval.id}`}>Your approver name</Label>
            <Input id={`approver-${approval.id}`} value={approver} onChange={(event) => setApprover(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`comments-${approval.id}`}>Comments (optional)</Label>
            <Textarea id={`comments-${approval.id}`} value={comments} onChange={(event) => setComments(event.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button onClick={() => handleDecide(true)} loading={decide.isPending}>
              Approve
            </Button>
            <Button variant="danger" onClick={() => handleDecide(false)} loading={decide.isPending}>
              Reject
            </Button>
          </div>
        </div>
      )}
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
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm">{value ? <time dateTime={value}>{new Date(value).toLocaleString()}</time> : "—"}</dd>
    </div>
  );
}
