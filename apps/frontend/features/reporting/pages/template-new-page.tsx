"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ParameterDeclarationsEditor } from "@/features/reporting/components/parameter-declarations-editor";
import { ReportDefinitionEditor } from "@/features/reporting/components/report-definition-editor";
import { useCreateTemplate } from "@/features/reporting/hooks/use-templates";
import { REPORT_CATEGORIES, REPORT_TYPES, type ParameterDeclaration, type ReportCategory, type ReportDefinition, type ReportTypeValue } from "@/features/reporting/types";
import { toast } from "@/state/toast-store";
import { useSelectedOrganization } from "@/organization/use-organizations";

const EMPTY_DEFINITION: ReportDefinition = { title: "", sections: [] };

/** `/reporting/templates/new` — the report designer (§7), scoped to
 * creating a brand-new template's first (`draft`) version. */
export function TemplateNewPage() {
  const router = useRouter();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const createTemplate = useCreateTemplate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ReportCategory | "">("");
  const [reportType, setReportType] = useState<ReportTypeValue | "">("");
  const [definition, setDefinition] = useState<ReportDefinition>(EMPTY_DEFINITION);
  const [parameters, setParameters] = useState<ParameterDeclaration[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedOrganizationId) return;
    if (!name.trim() || !category || !reportType || !definition.title.trim()) {
      setError("Name, category, type, and a definition title are required.");
      return;
    }
    setError(null);
    try {
      const template = await createTemplate.mutateAsync({
        organizationId: selectedOrganizationId,
        name: name.trim(),
        description: description.trim() || undefined,
        category,
        reportType,
        definition,
        parameters,
      });
      toast.success("Template created as draft");
      router.push(`/reporting/templates/${template.id}`);
    } catch {
      toast.danger("Failed to create template", "Check the designer document and try again.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="New template"
        description="Design a reusable report structure. Saved as a draft — approve it before generating reports from it."
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/reporting/templates")}>
            Back to Templates
          </Button>
        }
      />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="template-name">Name</Label>
                <Input id="template-name" value={name} onChange={(event) => setName(event.target.value)} required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="template-category">Category</Label>
                <Select id="template-category" value={category} onChange={(event) => setCategory(event.target.value as typeof category)} required>
                  <option value="">Select…</option>
                  {REPORT_CATEGORIES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="template-type">Type</Label>
                <Select id="template-type" value={reportType} onChange={(event) => setReportType(event.target.value as typeof reportType)} required>
                  <option value="">Select…</option>
                  {REPORT_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="template-description">Description</Label>
              <Textarea id="template-description" value={description} onChange={(event) => setDescription(event.target.value)} />
            </div>

            <div className="flex flex-col gap-1.5">
              <p className="text-sm font-medium">Designer</p>
              <ReportDefinitionEditor definition={definition} onChange={setDefinition} />
            </div>

            <div className="flex flex-col gap-1.5">
              <p className="text-sm font-medium">Parameters</p>
              <ParameterDeclarationsEditor parameters={parameters} onChange={setParameters} />
            </div>

            {error && <p className="text-danger text-sm">{error}</p>}

            <Button type="submit" loading={createTemplate.isPending} className="w-fit">
              Create template
            </Button>
          </form>
        )}
      </SectionState>
    </div>
  );
}
