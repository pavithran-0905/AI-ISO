"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/forms/checkbox";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { FilterClausesEditor } from "@/features/reporting/components/filter-clauses-editor";
import { ParameterValuesEditor } from "@/features/reporting/components/parameter-values-editor";
import { useTemplateParameters } from "@/features/reporting/hooks/use-templates";
import { EXPORT_FORMATS, type FilterClause, type Report, type ReportUpdateInput } from "@/features/reporting/types";

/**
 * Report editing (§6) — only the fields `PUT /reports/{id}` actually
 * accepts (`ReportUpdateRequest`): name, description, default format,
 * parameter values, filters, enabled. Category/type/template are fixed
 * at creation — there is no endpoint to change them afterward, so this
 * form doesn't offer to.
 */
export function ReportEditForm({
  report,
  onSubmit,
  isSubmitting,
}: {
  report: Report;
  onSubmit: (input: ReportUpdateInput) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState(report.name);
  const [description, setDescription] = useState(report.description ?? "");
  const [defaultFormat, setDefaultFormat] = useState(report.defaultFormat);
  const [parameterValues, setParameterValues] = useState<Record<string, unknown>>(report.parameterValues);
  const [filters, setFilters] = useState<FilterClause[]>(report.filters);
  const [enabled, setEnabled] = useState(report.enabled);
  const [error, setError] = useState<string | null>(null);

  const parametersQuery = useTemplateParameters(report.templateId);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setError(null);
    onSubmit({
      name: name.trim(),
      description: description.trim() || undefined,
      defaultFormat,
      parameterValues,
      filters,
      enabled,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="report-edit-name">Name</Label>
        <Input id="report-edit-name" value={name} onChange={(event) => setName(event.target.value)} required />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="report-edit-description">Description</Label>
        <Textarea id="report-edit-description" value={description} onChange={(event) => setDescription(event.target.value)} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="report-edit-format">Default export format</Label>
        <Select id="report-edit-format" value={defaultFormat} onChange={(event) => setDefaultFormat(event.target.value as typeof defaultFormat)} className="w-40">
          {EXPORT_FORMATS.map((format) => (
            <option key={format} value={format}>
              {format.toUpperCase()}
            </option>
          ))}
        </Select>
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

      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
        Enabled
      </label>

      {error && <p className="text-danger text-sm">{error}</p>}

      <Button type="submit" loading={isSubmitting} className="w-fit">
        Save changes
      </Button>
    </form>
  );
}
