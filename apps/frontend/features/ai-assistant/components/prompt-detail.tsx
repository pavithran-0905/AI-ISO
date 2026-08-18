"use client";

import { useMemo, useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Skeleton } from "@/components/feedback/skeleton";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import {
  useAddPromptVersion,
  useApprovePromptVersion,
  usePromptVersions,
  useRenderPrompt,
  useRollbackPrompt,
} from "@/features/ai-assistant/hooks/use-prompts";
import { PROMPT_STATUS_TONE } from "@/features/ai-assistant/lib/status-maps";
import type { Prompt } from "@/features/ai-assistant/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Nothing here is enforced server-side beyond basic state checks — any
 * caller can approve or roll back any prompt in the org (see
 * `docs/frontend/backend-v1-integration-limitations.md`). Mutating
 * actions (add version / approve / rollback) are hidden for a
 * non-administrative role as a UX-only precaution; rendering a preview
 * is left open to everyone since it changes nothing.
 */
export function PromptDetail({ prompt }: { prompt: Prompt }) {
  const { isAdministrative } = usePermissions();
  const versionsQuery = usePromptVersions(prompt.id);
  const addVersion = useAddPromptVersion(prompt.id);
  const approveVersion = useApprovePromptVersion(prompt.id);
  const rollbackPrompt = useRollbackPrompt(prompt.id);
  const renderPrompt = useRenderPrompt(prompt.id);

  const [newTemplate, setNewTemplate] = useState("");
  const [newVariablesInput, setNewVariablesInput] = useState("");
  const [renderValues, setRenderValues] = useState<Record<string, string>>({});

  const currentVersion = useMemo(
    () => versionsQuery.data?.find((version) => version.versionNumber === prompt.currentVersionNumber) ?? null,
    [versionsQuery.data, prompt.currentVersionNumber],
  );

  async function handleAddVersion(event: React.FormEvent) {
    event.preventDefault();
    if (!newTemplate.trim()) return;
    const variables = newVariablesInput.split(",").map((value) => value.trim()).filter(Boolean);
    try {
      await addVersion.mutateAsync({ template: newTemplate.trim(), variables });
      toast.success("Version added");
      setNewTemplate("");
      setNewVariablesInput("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not add version", message);
    }
  }

  async function handleApprove(versionNumber: string) {
    try {
      await approveVersion.mutateAsync(versionNumber);
      toast.success(`Version ${versionNumber} approved`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not approve version", message);
    }
  }

  async function handleRollback(versionNumber: string) {
    try {
      await rollbackPrompt.mutateAsync(versionNumber);
      toast.success(`Rolled back to version ${versionNumber}`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not roll back", message);
    }
  }

  async function handleRender(event: React.FormEvent) {
    event.preventDefault();
    try {
      await renderPrompt.mutateAsync(renderValues);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not render prompt", message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="font-medium">{prompt.name}</h3>
        {prompt.description && <p className="text-muted-foreground text-sm">{prompt.description}</p>}
      </div>

      <section className="flex flex-col gap-2">
        <p className="text-sm font-medium">Versions</p>
        {versionsQuery.isLoading && <Skeleton className="h-20 w-full" />}
        {versionsQuery.data && (
          <ul className="flex flex-col gap-2">
            {versionsQuery.data.map((version) => (
              <li key={version.id} className="border-border flex flex-col gap-1.5 rounded-md border p-2.5 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">v{version.versionNumber}</span>
                  <StatusBadge tone={PROMPT_STATUS_TONE[version.status]} label={version.status} />
                </div>
                <pre className="bg-muted overflow-x-auto rounded p-2 text-xs whitespace-pre-wrap">{version.template}</pre>
                {isAdministrative && version.status === "draft" && (
                  <Button variant="outline" onClick={() => void handleApprove(version.versionNumber)} loading={approveVersion.isPending} className="h-7 w-fit px-2 text-xs">
                    Approve
                  </Button>
                )}
                {isAdministrative && version.status === "approved" && version.versionNumber !== prompt.currentVersionNumber && (
                  <Button variant="outline" onClick={() => void handleRollback(version.versionNumber)} loading={rollbackPrompt.isPending} className="h-7 w-fit px-2 text-xs">
                    Roll back to this version
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {isAdministrative && (
        <section className="flex flex-col gap-2">
          <p className="text-sm font-medium">Add a version</p>
          <form onSubmit={handleAddVersion} className="flex flex-col gap-2">
            <Textarea value={newTemplate} onChange={(event) => setNewTemplate(event.target.value)} rows={4} placeholder="Template text" aria-label="New version template" />
            <Input value={newVariablesInput} onChange={(event) => setNewVariablesInput(event.target.value)} placeholder="Variables (comma-separated)" aria-label="New version variables" />
            <Button type="submit" variant="outline" loading={addVersion.isPending} disabled={!newTemplate.trim()} className="w-fit">
              Add version
            </Button>
          </form>
        </section>
      )}

      {currentVersion && currentVersion.variables.length > 0 && (
        <section className="flex flex-col gap-2">
          <p className="text-sm font-medium">Render current version</p>
          <form onSubmit={handleRender} className="flex flex-col gap-2">
            {currentVersion.variables.map((variable) => (
              <div key={variable} className="flex flex-col gap-1">
                <Label htmlFor={`render-${variable}`}>{variable}</Label>
                <Input
                  id={`render-${variable}`}
                  value={renderValues[variable] ?? ""}
                  onChange={(event) => setRenderValues((prev) => ({ ...prev, [variable]: event.target.value }))}
                />
              </div>
            ))}
            <Button type="submit" variant="outline" loading={renderPrompt.isPending} className="w-fit">
              Render
            </Button>
          </form>
          {renderPrompt.data && <pre className="bg-muted overflow-x-auto rounded p-2 text-xs whitespace-pre-wrap">{renderPrompt.data}</pre>}
        </section>
      )}
    </div>
  );
}
