"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { useRunAutomation } from "@/features/automation/hooks/use-jobs";
import {
  entriesToVariables,
  VariablesEditor,
  variablesToEntries,
  type VariableEntry,
} from "@/features/automation/components/variables-editor";
import { RUNNABLE_PLAYBOOK_TYPES, type AutomationJob } from "@/features/automation/types";
import { toast } from "@/state/toast-store";

type Step = "configure" | "confirm";

/**
 * The Run Automation flow (§10/§11/§38). Two explicit steps —
 * Configure, then a Review-and-Confirm summary showing exactly what
 * will run, where, and with which variables — because this genuinely
 * executes a script against infrastructure. The confirm button is
 * labeled "Run Automation", never something ambiguous like "Go"
 * (§11).
 *
 * Double-submission protection (§12): the confirm button carries the
 * mutation's own pending state (which disables it via `Button`'s
 * `loading` prop) and the flow waits for the backend's confirmed 201
 * before navigating. Nothing is retried automatically — §12 forbids
 * auto-retrying a potentially destructive action, and this endpoint
 * offers no idempotency key.
 *
 * Target selection (§16) is deliberately absent: `automation-service`
 * has a full `AutomationTarget` model and repository but **no routes
 * at all**, so targets can neither be listed nor created and a picker
 * would have nothing real to show. A run with no targets executes
 * locally on the automation-service container — which the confirmation
 * step states explicitly rather than leaving implied.
 */
export function RunAutomationDialog({ job, open, onClose }: { job: AutomationJob; open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [step, setStep] = useState<Step>("configure");
  const [entries, setEntries] = useState<VariableEntry[]>(() => variablesToEntries(job.variables));
  const [timeoutSeconds, setTimeoutSeconds] = useState(job.timeoutSeconds ? String(job.timeoutSeconds) : "");
  const runAutomation = useRunAutomation(job.id);

  const isRunnable = RUNNABLE_PLAYBOOK_TYPES.has(job.playbookType);

  function handleClose() {
    setStep("configure");
    onClose();
  }

  async function handleRun() {
    try {
      const execution = await runAutomation.mutateAsync({
        variables: entriesToVariables(entries),
        timeoutSeconds: timeoutSeconds ? Number(timeoutSeconds) : null,
      });
      toast.success("Automation started", "Follow its progress on the execution page.");
      handleClose();
      router.push(`/automation/executions/${execution.id}`);
    } catch {
      toast.danger("Could not start this automation", "Nothing was run. Please try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title={step === "configure" ? `Run ${job.name}` : "Confirm this run"}
      description={step === "configure" ? "Review the variables this run will use." : undefined}
      className="max-w-lg"
      footer={
        step === "configure" ? (
          <>
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button onClick={() => setStep("confirm")}>Review</Button>
          </>
        ) : (
          <>
            <Button variant="outline" onClick={() => setStep("configure")} disabled={runAutomation.isPending}>
              Back
            </Button>
            <Button onClick={handleRun} loading={runAutomation.isPending}>
              Run Automation
            </Button>
          </>
        )
      }
    >
      {step === "configure" ? (
        <div className="flex flex-col gap-4">
          {!isRunnable && (
            <Alert tone="warning" title="This playbook type can't be executed yet">
              AI-IOS can currently run shell, bash, Python, PowerShell, and Ansible content. A{" "}
              {job.playbookType.replace(/_/g, " ")} automation will fail when dispatched.
            </Alert>
          )}
          <VariablesEditor
            entries={entries}
            onChange={setEntries}
            description="Stored with the run for reference. AI-IOS does not substitute variables into the script content."
          />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="run-timeout">Timeout (seconds)</Label>
            <Input
              id="run-timeout"
              type="number"
              min={1}
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(event.target.value)}
              placeholder="Use the automation's own timeout"
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <Alert tone="warning" title="This runs real automation content">
            Running this executes the automation&rsquo;s script. Make sure the details below are what you expect.
          </Alert>
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <Field label="Automation" value={job.name} />
            <Field label="Type" value={job.automationType.replace(/_/g, " ")} />
            <Field label="Playbook" value={job.playbookType.replace(/_/g, " ")} />
            <Field label="Timeout" value={timeoutSeconds ? `${timeoutSeconds}s` : "Automation default"} />
            <Field label="Runs on" value="The AI-IOS automation host (no targets are configurable)" />
          </dl>
          <div>
            <p className="text-muted-foreground mb-1 text-xs">Variables</p>
            {entries.filter((entry) => entry.key.trim()).length === 0 ? (
              <p className="text-sm">None</p>
            ) : (
              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                {entries
                  .filter((entry) => entry.key.trim())
                  .map((entry) => (
                    <div key={entry.key} className="contents">
                      <dt className="text-muted-foreground font-mono text-xs">{entry.key}</dt>
                      <dd className="font-mono text-xs">{entry.value || "—"}</dd>
                    </div>
                  ))}
              </dl>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}
