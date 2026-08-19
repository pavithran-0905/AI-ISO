"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Textarea } from "@/components/forms/textarea";
import { usePatchProject } from "@/features/settings/hooks/use-project-settings";
import type { ProjectSummary } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/** `PATCH /projects/{id}` — genuinely partial (`exclude_unset`), used
 * over this service's own `PUT` for the same "PATCH, never PUT"
 * reason established in Prompt 011. */
export function ProjectIdentityForm({ project, canEdit }: { project: ProjectSummary; canEdit: boolean }) {
  const patchProject = usePatchProject();
  const [name, setName] = useState(project.name);
  const [displayName, setDisplayName] = useState(project.displayName ?? "");
  const [description, setDescription] = useState(project.description ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await patchProject.mutateAsync({
        projectId: project.id,
        input: { name, displayName: displayName || undefined, description: description || undefined },
      });
      toast.success("Project updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update project", message);
    }
  }

  if (!canEdit) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>Your role doesn&apos;t allow editing this project.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          <p className="font-medium">{project.displayName ?? project.name}</p>
          {project.description && <p className="text-muted-foreground">{project.description}</p>}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Identity</CardTitle>
        <CardDescription>Name and description for this project.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Name" required>
              {(fieldProps) => <Input {...fieldProps} value={name} onChange={(event) => setName(event.target.value)} required />}
            </FormField>
            <FormField label="Display name">
              {(fieldProps) => <Input {...fieldProps} value={displayName} onChange={(event) => setDisplayName(event.target.value)} />}
            </FormField>
          </div>
          <FormField label="Description">
            {(fieldProps) => <Textarea {...fieldProps} value={description} onChange={(event) => setDescription(event.target.value)} />}
          </FormField>
          <Button type="submit" loading={patchProject.isPending} className="w-fit">
            Save project
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
