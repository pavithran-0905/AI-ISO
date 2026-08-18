"use client";

import { Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { AUTOMATION_TYPES, JOB_STATUSES, type AutomationTypeValue, type JobStatusValue } from "@/features/automation/types";

export interface JobFilterValues {
  query: string;
  status: JobStatusValue | "";
  automationType: AutomationTypeValue | "";
}

export const EMPTY_JOB_FILTERS: JobFilterValues = { query: "", status: "", automationType: "" };

/**
 * All three filters are applied client-side (§24: "do not create fake
 * filters" — these are real, they just can't be pushed to the server).
 * `GET /automation/jobs` accepts only `organization_id`, with no
 * search, filter, sort, or pagination params at all — but it also
 * returns the organization's complete job list unpaginated, so
 * filtering here operates on everything and hides nothing.
 */
export function JobFilters({
  values,
  onChange,
  onReset,
}: {
  values: JobFilterValues;
  onChange: (values: JobFilterValues) => void;
  onReset: () => void;
}) {
  const activeFilterCount = [values.query, values.status, values.automationType].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="job-search">Search</Label>
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            id="job-search"
            value={values.query}
            onChange={(event) => onChange({ ...values, query: event.target.value })}
            placeholder="Name, description, or tag…"
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="job-status-filter">Status</Label>
        <Select
          id="job-status-filter"
          value={values.status}
          onChange={(event) => onChange({ ...values, status: event.target.value as JobStatusValue | "" })}
          className="w-36"
        >
          <option value="">All statuses</option>
          {JOB_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="job-type-filter">Type</Label>
        <Select
          id="job-type-filter"
          value={values.automationType}
          onChange={(event) => onChange({ ...values, automationType: event.target.value as AutomationTypeValue | "" })}
          className="w-52"
        >
          <option value="">All types</option>
          {AUTOMATION_TYPES.map((type) => (
            <option key={type} value={type}>
              {type.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
      </div>

      {activeFilterCount > 0 && (
        <Button variant="ghost" onClick={onReset} className="gap-1.5">
          <X className="size-4" aria-hidden="true" />
          Reset
          <Badge variant="outline">{activeFilterCount}</Badge>
        </Button>
      )}
    </div>
  );
}
