"use client";

import { useState } from "react";

import { SectionState } from "@/features/dashboard/components/section-state";
import { Button } from "@/components/ui/button";
import { ParameterDeclarationsEditor } from "@/features/reporting/components/parameter-declarations-editor";
import { ReportDefinitionEditor } from "@/features/reporting/components/report-definition-editor";
import { useAddTemplateVersion, useTemplateParameters } from "@/features/reporting/hooks/use-templates";
import type { ParameterDeclaration, ReportDefinition, ReportTemplate } from "@/features/reporting/types";
import { toast } from "@/state/toast-store";

/** Adds a new `draft`, minor-bumped version (§7) — pre-filled from the
 * currently-viewed version's own definition/parameters, since a new
 * version replaces the whole document atomically rather than patching
 * it (confirmed: no partial "update one section" endpoint exists).
 * Waits for the current parameter declarations to load before
 * mounting the actual editable form, so its local state can be
 * initialized once from real data instead of synced in via an effect.
 */
export function TemplateNewVersionForm({ template, onSaved }: { template: ReportTemplate; onSaved: () => void }) {
  const parametersQuery = useTemplateParameters(template.id);

  return (
    <SectionState isLoading={parametersQuery.isLoading} isError={parametersQuery.isError} error={parametersQuery.error} onRetry={() => parametersQuery.refetch()}>
      {parametersQuery.data && (
        <VersionForm templateId={template.id} initialDefinition={template.definition} initialParameters={parametersQuery.data} onSaved={onSaved} />
      )}
    </SectionState>
  );
}

function VersionForm({
  templateId,
  initialDefinition,
  initialParameters,
  onSaved,
}: {
  templateId: string;
  initialDefinition: ReportDefinition;
  initialParameters: ParameterDeclaration[];
  onSaved: () => void;
}) {
  const [definition, setDefinition] = useState(initialDefinition);
  const [parameters, setParameters] = useState(initialParameters);
  const addVersion = useAddTemplateVersion(templateId);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await addVersion.mutateAsync({ definition, parameters });
      toast.success("New draft version created");
      onSaved();
    } catch {
      toast.danger("Failed to save new version", "Check the designer document and try again.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <ReportDefinitionEditor definition={definition} onChange={setDefinition} />
      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-medium">Parameters</p>
        <ParameterDeclarationsEditor parameters={parameters} onChange={setParameters} />
      </div>
      <Button type="submit" loading={addVersion.isPending} className="w-fit">
        Save as new draft version
      </Button>
    </form>
  );
}
