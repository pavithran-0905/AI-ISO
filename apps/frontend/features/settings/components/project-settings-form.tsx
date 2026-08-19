"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { useUpdateProjectSettings } from "@/features/settings/hooks/use-project-settings";
import type { ProjectSettings } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `GET/PUT /projects/{id}/settings` — full-replace `PUT` (confirmed:
 * no `PATCH` exists for this sub-resource, unlike the project's own
 * core resource). Only the three well-typed scalar fields are
 * editable — every policy field (`retentionPolicies`,
 * `executionPolicies`, `automationPolicies`, `validationPolicies`,
 * `monitoringPolicies`, `aiSettings`, `storagePolicies`,
 * `securityPolicies`, `notificationSettings`) is an opaque JSON blob
 * with no defined sub-schema, round-tripped unchanged.
 */
export function ProjectSettingsForm({ projectId, settings, canEdit }: { projectId: string; settings: ProjectSettings; canEdit: boolean }) {
  const updateSettings = useUpdateProjectSettings(projectId);
  const [defaultEnvironment, setDefaultEnvironment] = useState(settings.defaultEnvironment ?? "");
  const [defaultConnectorId, setDefaultConnectorId] = useState(settings.defaultConnectorId ?? "");
  const [defaultWorkflowRuntime, setDefaultWorkflowRuntime] = useState(settings.defaultWorkflowRuntime ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updateSettings.mutateAsync({
        ...settings,
        defaultEnvironment: defaultEnvironment || null,
        defaultConnectorId: defaultConnectorId || null,
        defaultWorkflowRuntime: defaultWorkflowRuntime || null,
      });
      toast.success("Project settings updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update project settings", message);
    }
  }

  if (!canEdit) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Defaults</CardTitle>
          <CardDescription>Your role doesn&apos;t allow editing this project.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          <p>Default environment: {settings.defaultEnvironment ?? "Not set"}</p>
          <p>Default workflow runtime: {settings.defaultWorkflowRuntime ?? "Not set"}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Defaults</CardTitle>
        <CardDescription>Applied when a resource in this project doesn&apos;t specify its own.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <FormField label="Default environment">
              {(fieldProps) => <Input {...fieldProps} value={defaultEnvironment} onChange={(event) => setDefaultEnvironment(event.target.value)} />}
            </FormField>
            <FormField label="Default connector ID" description="Raw id — no picker exists for this yet.">
              {(fieldProps) => <Input {...fieldProps} value={defaultConnectorId} onChange={(event) => setDefaultConnectorId(event.target.value)} className="font-mono" />}
            </FormField>
            <FormField label="Default workflow runtime">
              {(fieldProps) => <Input {...fieldProps} value={defaultWorkflowRuntime} onChange={(event) => setDefaultWorkflowRuntime(event.target.value)} />}
            </FormField>
          </div>
          <Button type="submit" loading={updateSettings.isPending} className="w-fit">
            Save defaults
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
