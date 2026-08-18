"use client";

import { useState } from "react";

import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import {
  entriesToVariables,
  VariablesEditor,
  variablesToEntries,
  type VariableEntry,
} from "@/features/automation/components/variables-editor";
import {
  AUTOMATION_TYPES,
  EXECUTION_MODES,
  JOB_STATUSES,
  PLAYBOOK_TYPES,
  RUNNABLE_PLAYBOOK_TYPES,
  type AutomationJob,
  type AutomationTypeValue,
  type ExecutionModeValue,
  type JobStatusValue,
  type PlaybookTypeValue,
} from "@/features/automation/types";

export interface JobFormValues {
  name: string;
  description: string;
  status: JobStatusValue;
  automationType: AutomationTypeValue;
  playbookType: PlaybookTypeValue;
  executionMode: ExecutionModeValue;
  content: string;
  variables: Record<string, unknown>;
  tags: string[];
  timeoutSeconds: number | null;
}

/**
 * Create/edit an automation job.
 *
 * The `status` control only appears when editing, and that is a real
 * safety requirement rather than a preference: `PUT /automation/jobs/{id}`
 * is a **full replace** whose schema defaults `status` to `draft`, so
 * an update that omits it silently demotes a live automation. The
 * field is therefore always present and always pre-filled with the
 * job's current status on edit. On create the backend hard-codes
 * `active` and ignores any client value, so offering the control there
 * would be a lie. See
 * `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function JobForm({
  job,
  onSubmit,
  isSubmitting,
  submitLabel,
}: {
  job?: AutomationJob;
  onSubmit: (values: JobFormValues) => void;
  isSubmitting: boolean;
  submitLabel: string;
}) {
  const isEdit = job !== undefined;
  const [name, setName] = useState(job?.name ?? "");
  const [description, setDescription] = useState(job?.description ?? "");
  const [status, setStatus] = useState<JobStatusValue>(job?.status ?? "active");
  const [automationType, setAutomationType] = useState<AutomationTypeValue | "">(job?.automationType ?? "");
  const [playbookType, setPlaybookType] = useState<PlaybookTypeValue | "">(job?.playbookType ?? "");
  const [executionMode, setExecutionMode] = useState<ExecutionModeValue>(job?.executionMode ?? "manual");
  const [content, setContent] = useState(job?.content ?? "");
  const [entries, setEntries] = useState<VariableEntry[]>(() => variablesToEntries(job?.variables ?? {}));
  const [tags, setTags] = useState(job?.tags.join(", ") ?? "");
  const [timeoutSeconds, setTimeoutSeconds] = useState(job?.timeoutSeconds ? String(job.timeoutSeconds) : "");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !automationType || !playbookType || !content.trim()) {
      setError("Name, type, playbook type, and content are all required.");
      return;
    }
    setError(null);
    onSubmit({
      name: name.trim(),
      description: description.trim(),
      status,
      automationType,
      playbookType,
      executionMode,
      content,
      variables: entriesToVariables(entries),
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      timeoutSeconds: timeoutSeconds ? Number(timeoutSeconds) : null,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="job-name">Name</Label>
        <Input id="job-name" value={name} onChange={(event) => setName(event.target.value)} required />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="job-description">Description</Label>
        <Textarea id="job-description" value={description} onChange={(event) => setDescription(event.target.value)} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="job-automation-type">Type</Label>
          <Select
            id="job-automation-type"
            value={automationType}
            onChange={(event) => setAutomationType(event.target.value as AutomationTypeValue)}
            required
          >
            <option value="">Select…</option>
            {AUTOMATION_TYPES.map((value) => (
              <option key={value} value={value}>
                {value.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="job-playbook-type">Playbook type</Label>
          <Select
            id="job-playbook-type"
            value={playbookType}
            onChange={(event) => setPlaybookType(event.target.value as PlaybookTypeValue)}
            required
          >
            <option value="">Select…</option>
            {PLAYBOOK_TYPES.map((value) => (
              <option key={value} value={value}>
                {value.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="job-execution-mode">Execution mode</Label>
          <Select
            id="job-execution-mode"
            value={executionMode}
            onChange={(event) => setExecutionMode(event.target.value as ExecutionModeValue)}
          >
            {EXECUTION_MODES.map((value) => (
              <option key={value} value={value}>
                {value.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </div>

        {isEdit && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="job-status">Status</Label>
            <Select id="job-status" value={status} onChange={(event) => setStatus(event.target.value as JobStatusValue)}>
              {JOB_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="job-timeout">Timeout (seconds)</Label>
          <Input
            id="job-timeout"
            type="number"
            min={1}
            value={timeoutSeconds}
            onChange={(event) => setTimeoutSeconds(event.target.value)}
            placeholder="No timeout"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="job-tags">Tags (comma-separated)</Label>
          <Input id="job-tags" value={tags} onChange={(event) => setTags(event.target.value)} />
        </div>
      </div>

      {playbookType !== "" && !RUNNABLE_PLAYBOOK_TYPES.has(playbookType) && (
        <Alert tone="warning" title="This playbook type can't be executed yet">
          AI-IOS can currently run shell, bash, Python, PowerShell, and Ansible content. You can still save this
          automation, but running it will fail when it reaches the dispatcher.
        </Alert>
      )}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="job-content">Content</Label>
        <Textarea
          id="job-content"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          className="min-h-48 font-mono text-xs"
          required
        />
      </div>

      <VariablesEditor
        entries={entries}
        onChange={setEntries}
        label="Default variables"
        description="Merged into every run and stored with it. Not substituted into the script content."
      />

      {error && <p className="text-danger text-sm">{error}</p>}

      <Button type="submit" loading={isSubmitting} className="w-fit">
        {submitLabel}
      </Button>
    </form>
  );
}
