"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/feedback/status-badge";
import { DefinitionSummary } from "@/features/reporting/components/definition-summary";
import { TemplateNewVersionForm } from "@/features/reporting/components/template-new-version-form";
import { TemplateVersionsList } from "@/features/reporting/components/template-versions-list";
import { useApproveTemplate, useArchiveTemplate } from "@/features/reporting/hooks/use-templates";
import { TEMPLATE_STATUS_TONE } from "@/features/reporting/lib/status-tones";
import type { ReportTemplate } from "@/features/reporting/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Template Detail (§7) — Identity → Definition → Versions → Actions.
 * Approve/Archive are real state-machine transitions
 * (`draft → approved → archived`); a new version always starts back at
 * `draft` and needs its own approval before reports can generate
 * against it (`resolve_for_execution()` refuses anything else).
 */
export function TemplateDetailView({ template }: { template: ReportTemplate }) {
  const { can } = usePermissions();
  const [addingVersion, setAddingVersion] = useState(false);
  const approveTemplate = useApproveTemplate();
  const archiveTemplate = useArchiveTemplate();

  async function handleApprove() {
    try {
      await approveTemplate.mutateAsync(template.id);
      toast.success("Template approved");
    } catch {
      toast.danger("Failed to approve template");
    }
  }

  async function handleArchive() {
    try {
      await archiveTemplate.mutateAsync(template.id);
      toast.success("Template archived");
    } catch {
      toast.danger("Failed to archive template");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">Category</dt>
              <dd>{template.category}</dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">Type</dt>
              <dd>{template.reportType}</dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">Version</dt>
              <dd>{template.versionNumber}</dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">Status</dt>
              <dd>
                <StatusBadge tone={TEMPLATE_STATUS_TONE[template.status]} label={template.status} />
              </dd>
            </div>
          </dl>
          {template.description && <p className="text-muted-foreground mt-4 text-sm">{template.description}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {can("approve") && template.status === "draft" && (
            <Button onClick={handleApprove} loading={approveTemplate.isPending}>
              Approve
            </Button>
          )}
          {can("update") && template.status !== "archived" && !addingVersion && (
            <Button variant="outline" onClick={() => setAddingVersion(true)}>
              Add new version
            </Button>
          )}
          {can("delete") && template.status !== "archived" && (
            <Button variant="danger" onClick={handleArchive} loading={archiveTemplate.isPending}>
              Archive
            </Button>
          )}
        </CardContent>
      </Card>

      {addingVersion && (
        <Card>
          <CardHeader>
            <CardTitle>New version</CardTitle>
          </CardHeader>
          <CardContent>
            <TemplateNewVersionForm template={template} onSaved={() => setAddingVersion(false)} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Definition</CardTitle>
        </CardHeader>
        <CardContent>
          <DefinitionSummary definition={template.definition} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Versions</CardTitle>
        </CardHeader>
        <CardContent>
          <TemplateVersionsList templateId={template.id} />
        </CardContent>
      </Card>
    </div>
  );
}
