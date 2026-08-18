"use client";

import { Ban, Pause, Play, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { RunAutomationDialog } from "@/features/automation/components/run-automation-dialog";
import {
  useCancelAutomation,
  useDeleteAutomationJob,
  usePauseAutomation,
  useResumeAutomation,
} from "@/features/automation/hooks/use-jobs";
import type { AutomationJob } from "@/features/automation/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

type ConfirmKind = "cancel" | "delete" | null;

/**
 * Run / Pause / Resume / Cancel / Edit / Delete (§10–§12, §19–§20) —
 * the exact mutation set `automation-service` really exposes.
 *
 * Notably absent: **Retry**. §19 asks for it "if V1 supports retry" —
 * there is no retry route. The backend does retry transient failures
 * internally during dispatch, but that history has no endpoint either.
 * Re-running is done through Run Automation, which is honest about
 * being a fresh run rather than a resumed one.
 *
 * Cancel/Pause/Resume act on the job's own currently-active execution
 * (the backend resolves which); each returns a 404-style error when
 * nothing is running, surfaced as the backend's own message rather
 * than a guess. Cancel requires confirmation (§20) and the UI never
 * claims "Cancelled" until the backend confirms it — the button waits
 * on the real mutation result.
 */
export function JobActions({ job }: { job: AutomationJob }) {
  const router = useRouter();
  const { can } = usePermissions();
  const [runOpen, setRunOpen] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmKind>(null);

  const cancelAutomation = useCancelAutomation();
  const pauseAutomation = usePauseAutomation();
  const resumeAutomation = useResumeAutomation();
  const deleteJob = useDeleteAutomationJob();

  const isBusy = cancelAutomation.isPending || pauseAutomation.isPending || resumeAutomation.isPending;

  function reportFailure(action: string, error: unknown) {
    const message = error instanceof ApiRequestError ? error.message : "Please try again.";
    toast.danger(`Could not ${action} this automation`, message);
  }

  async function handlePause() {
    try {
      await pauseAutomation.mutateAsync(job.id);
      toast.success("Run paused");
    } catch (error) {
      reportFailure("pause", error);
    }
  }

  async function handleResume() {
    try {
      await resumeAutomation.mutateAsync(job.id);
      // The resume response still reports `paused` — the backend only
      // flips the status once its worker picks the run back up — so the
      // message deliberately says "resuming", not "resumed".
      toast.success("Resuming run", "It will show as running once a worker picks it up.");
    } catch (error) {
      reportFailure("resume", error);
    }
  }

  async function handleCancel() {
    try {
      await cancelAutomation.mutateAsync(job.id);
      toast.success("Run cancelled", "Work already in flight may take a moment to stop.");
      setConfirm(null);
    } catch (error) {
      reportFailure("cancel", error);
    }
  }

  async function handleDelete() {
    try {
      await deleteJob.mutateAsync(job.id);
      toast.success("Automation deleted");
      router.push("/automation/automations");
    } catch (error) {
      reportFailure("delete", error);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {can("execute") && (
        <Button onClick={() => setRunOpen(true)} className="gap-1.5">
          <Play className="size-4" aria-hidden="true" />
          Run Automation
        </Button>
      )}
      {can("execute") && (
        <Button variant="outline" onClick={handlePause} loading={pauseAutomation.isPending} disabled={isBusy} className="gap-1.5">
          <Pause className="size-4" aria-hidden="true" />
          Pause run
        </Button>
      )}
      {can("execute") && (
        <Button variant="outline" onClick={handleResume} loading={resumeAutomation.isPending} disabled={isBusy}>
          Resume run
        </Button>
      )}
      {can("execute") && (
        <Button variant="outline" onClick={() => setConfirm("cancel")} disabled={isBusy} className="gap-1.5">
          <Ban className="size-4" aria-hidden="true" />
          Cancel run
        </Button>
      )}
      {can("update") && (
        <Link href={`/automation/automations/${job.id}/edit`} className={buttonVariants("outline")}>
          Edit
        </Link>
      )}
      {can("delete") && (
        <Button variant="danger" onClick={() => setConfirm("delete")} className="gap-1.5">
          <Trash2 className="size-4" aria-hidden="true" />
          Delete
        </Button>
      )}

      <RunAutomationDialog job={job} open={runOpen} onClose={() => setRunOpen(false)} />

      <Dialog
        open={confirm === "cancel"}
        onClose={() => setConfirm(null)}
        title={`Cancel the running ${job.name}?`}
        description="AI-IOS stops scheduling further work immediately. Anything already in flight finishes on its own."
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirm(null)} disabled={cancelAutomation.isPending}>
              Keep running
            </Button>
            <Button variant="danger" onClick={handleCancel} loading={cancelAutomation.isPending}>
              Cancel run
            </Button>
          </>
        }
      />

      <Dialog
        open={confirm === "delete"}
        onClose={() => setConfirm(null)}
        title={`Delete ${job.name}?`}
        description="It disappears from every list. Past executions are kept."
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirm(null)} disabled={deleteJob.isPending}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleteJob.isPending}>
              Delete
            </Button>
          </>
        }
      />
    </div>
  );
}
