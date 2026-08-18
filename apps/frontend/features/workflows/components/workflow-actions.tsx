"use client";

import { Ban, Pause, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import {
  entriesToVariables,
  VariablesEditor,
  variablesToEntries,
  type VariableEntry,
} from "@/features/automation/components/variables-editor";
import {
  useCancelWorkflow,
  useExecuteWorkflow,
  usePauseWorkflow,
  useResumeWorkflow,
} from "@/features/workflows/hooks/use-workflows";
import type { Workflow } from "@/features/workflows/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Run / Pause / Resume / Cancel for a workflow definition (§10–§12,
 * §20). Same safety posture as `JobActions`: a two-step run flow with
 * an explicit confirmation summary, an unambiguous "Run Workflow"
 * label, no optimistic updates, and confirmation before cancelling.
 *
 * Pause/resume/cancel act on this workflow's own currently-active
 * instance (the backend resolves which and 404s when there isn't one),
 * and — per the service's own documentation — they are cooperative
 * metadata transitions: a node already executing runs to completion.
 * The UI says so rather than implying an immediate halt.
 *
 * Rollback and replay routes exist but are not surfaced — see
 * `docs/frontend/rfi/automation.md`.
 */
export function WorkflowActions({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const { can } = usePermissions();
  const [runOpen, setRunOpen] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [entries, setEntries] = useState<VariableEntry[]>(() => variablesToEntries(workflow.defaultVariables));

  const executeWorkflow = useExecuteWorkflow(workflow.id);
  const pauseWorkflow = usePauseWorkflow();
  const resumeWorkflow = useResumeWorkflow();
  const cancelWorkflow = useCancelWorkflow();

  const isBusy = pauseWorkflow.isPending || resumeWorkflow.isPending || cancelWorkflow.isPending;

  function reportFailure(action: string, error: unknown) {
    const message = error instanceof ApiRequestError ? error.message : "Please try again.";
    toast.danger(`Could not ${action} this workflow`, message);
  }

  async function handleRun() {
    try {
      const instance = await executeWorkflow.mutateAsync(entriesToVariables(entries));
      toast.success("Workflow started", "Follow its progress on the instance page.");
      setRunOpen(false);
      router.push(`/workflows/instances/${instance.id}`);
    } catch (error) {
      reportFailure("start", error);
    }
  }

  async function handleControl(action: "pause" | "resume" | "cancel") {
    const mutation = action === "pause" ? pauseWorkflow : action === "resume" ? resumeWorkflow : cancelWorkflow;
    try {
      await mutation.mutateAsync(workflow.id);
      toast.success(`Workflow ${action === "cancel" ? "cancelled" : `${action}d`}`, "Work already in flight finishes on its own.");
      setConfirmCancel(false);
    } catch (error) {
      reportFailure(action, error);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {can("execute") && (
        <Button onClick={() => setRunOpen(true)} className="gap-1.5">
          <Play className="size-4" aria-hidden="true" />
          Run Workflow
        </Button>
      )}
      {can("execute") && (
        <Button variant="outline" onClick={() => handleControl("pause")} loading={pauseWorkflow.isPending} disabled={isBusy} className="gap-1.5">
          <Pause className="size-4" aria-hidden="true" />
          Pause run
        </Button>
      )}
      {can("execute") && (
        <Button variant="outline" onClick={() => handleControl("resume")} loading={resumeWorkflow.isPending} disabled={isBusy}>
          Resume run
        </Button>
      )}
      {can("execute") && (
        <Button variant="outline" onClick={() => setConfirmCancel(true)} disabled={isBusy} className="gap-1.5">
          <Ban className="size-4" aria-hidden="true" />
          Cancel run
        </Button>
      )}

      <Dialog
        open={runOpen}
        onClose={() => setRunOpen(false)}
        title={`Run ${workflow.name}`}
        description="These variables are passed to the run. Review them before starting."
        className="max-w-lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setRunOpen(false)} disabled={executeWorkflow.isPending}>
              Cancel
            </Button>
            <Button onClick={handleRun} loading={executeWorkflow.isPending}>
              Run Workflow
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Alert tone="warning" title="This runs a real workflow">
            Starting this executes every node in the workflow&rsquo;s current version ({workflow.currentVersionNumber ?? "unversioned"}).
          </Alert>
          <VariablesEditor
            entries={entries}
            onChange={setEntries}
            description="Passed to the run itself. AI-IOS does not store them on the instance, so they won't appear on the instance page afterward."
          />
        </div>
      </Dialog>

      <Dialog
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        title={`Cancel the running ${workflow.name}?`}
        description="AI-IOS stops scheduling further nodes immediately. A node already executing finishes on its own."
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmCancel(false)} disabled={cancelWorkflow.isPending}>
              Keep running
            </Button>
            <Button variant="danger" onClick={() => handleControl("cancel")} loading={cancelWorkflow.isPending}>
              Cancel run
            </Button>
          </>
        }
      />
    </div>
  );
}
