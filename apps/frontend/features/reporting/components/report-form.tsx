"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { FilterClausesEditor } from "@/features/reporting/components/filter-clauses-editor";
import { ParameterValuesEditor } from "@/features/reporting/components/parameter-values-editor";
import { useTemplateParameters, useTemplates } from "@/features/reporting/hooks/use-templates";
import { EXPORT_FORMATS, REPORT_CATEGORIES, REPORT_TYPES, type FilterClause, type ReportCreateInput } from "@/features/reporting/types";

/**
 * Report creation form (§8). `category`/`reportType`/`templateId` are
 * only settable at creation — `PUT /reports/{id}` has no fields for
 * them (confirmed by source inspection of `ReportUpdateRequest`), so
 * this form is deliberately create-only; editing an existing report
 * uses `ReportEditForm` instead, which exposes only the fields the
 * backend actually lets you change.
 *
 * Only `APPROVED` templates are offered — generation itself refuses to
 * run against anything else (`resolve_for_execution()`).
 */
export function ReportForm({
  organizationId,
  onSubmit,
  isSubmitting,
}: {
  organizationId: string;
  onSubmit: (input: ReportCreateInput) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ReportCreateInput["category"] | "">("");
  const [reportType, setReportType] = useState<ReportCreateInput["reportType"] | "">("");
  const [templateId, setTemplateId] = useState("");
  const [defaultFormat, setDefaultFormat] = useState<ReportCreateInput["defaultFormat"]>("pdf");
  const [parameterValues, setParameterValues] = useState<Record<string, unknown>>({});
  const [filters, setFilters] = useState<FilterClause[]>([]);
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useTemplates(organizationId);
  const approvedTemplates = useMemo(() => (templatesQuery.data ?? []).filter((template) => template.status === "approved"), [templatesQuery.data]);
  const parametersQuery = useTemplateParameters(templateId || null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!category || !reportType) {
      setError("Category and type are required.");
      return;
    }
    setError(null);
    onSubmit({
      organizationId,
      name: name.trim(),
      description: description.trim() || undefined,
      category,
      reportType,
      templateId: templateId || undefined,
      defaultFormat,
      parameterValues,
      filters,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="report-name">Name</Label>
        <Input id="report-name" value={name} onChange={(event) => setName(event.target.value)} required />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="report-description">Description</Label>
        <Textarea id="report-description" value={description} onChange={(event) => setDescription(event.target.value)} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="report-category">Category</Label>
          <Select id="report-category" value={category} onChange={(event) => setCategory(event.target.value as typeof category)} required>
            <option value="">Select…</option>
            {REPORT_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="report-type">Type</Label>
          <Select id="report-type" value={reportType} onChange={(event) => setReportType(event.target.value as typeof reportType)} required>
            <option value="">Select…</option>
            {REPORT_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="report-template">Template</Label>
          <Select id="report-template" value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
            <option value="">No template</option>
            {approvedTemplates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name} (v{template.versionNumber})
              </option>
            ))}
          </Select>
          {templateId === "" && <p className="text-muted-foreground text-xs">A report needs an approved template before it can be generated.</p>}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="report-format">Default export format</Label>
          <Select id="report-format" value={defaultFormat} onChange={(event) => setDefaultFormat(event.target.value as typeof defaultFormat)}>
            {EXPORT_FORMATS.map((format) => (
              <option key={format} value={format}>
                {format.toUpperCase()}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {parametersQuery.data && parametersQuery.data.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-medium">Parameters</p>
          <ParameterValuesEditor parameters={parametersQuery.data} values={parameterValues} onChange={setParameterValues} />
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-medium">Filters</p>
        <FilterClausesEditor clauses={filters} onChange={setFilters} />
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      <Button type="submit" loading={isSubmitting} className="w-fit">
        Create report
      </Button>
    </form>
  );
}
