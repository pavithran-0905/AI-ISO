"use client";

import { Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Checkbox } from "@/components/forms/checkbox";
import { REPORT_CATEGORIES, type ReportCategory } from "@/features/reporting/types";

export interface ReportFilterValues {
  query: string;
  category: ReportCategory | "";
  enabledOnly: boolean;
}

export const EMPTY_REPORT_FILTERS: ReportFilterValues = { query: "", category: "", enabledOnly: false };

/**
 * `category`/`enabled_only` are real `GET /reports` query params
 * (server-side). `query` is a client-side text search over
 * name/description — honest here specifically because `GET /reports`
 * returns its full, unpaginated result for the given category/enabled
 * filter, so there is no hidden remainder a client-side search could
 * silently miss (§23).
 */
export function ReportFilters({
  values,
  onChange,
  onReset,
}: {
  values: ReportFilterValues;
  onChange: (values: ReportFilterValues) => void;
  onReset: () => void;
}) {
  const activeFilterCount = [values.query, values.category, values.enabledOnly || ""].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="report-search">Search</Label>
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            id="report-search"
            value={values.query}
            onChange={(event) => onChange({ ...values, query: event.target.value })}
            placeholder="Name or description…"
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="report-category-filter">Category</Label>
        <Select
          id="report-category-filter"
          value={values.category}
          onChange={(event) => onChange({ ...values, category: event.target.value as ReportCategory | "" })}
          className="w-44"
        >
          <option value="">All categories</option>
          {REPORT_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </Select>
      </div>

      <label className="flex items-center gap-2 pb-2 text-sm">
        <Checkbox
          checked={values.enabledOnly}
          onChange={(event) => onChange({ ...values, enabledOnly: event.target.checked })}
        />
        Enabled only
      </label>

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
