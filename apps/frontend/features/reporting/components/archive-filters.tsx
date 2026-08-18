"use client";

import { Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { ARCHIVE_STATUSES, type ArchiveStatusValue } from "@/features/reporting/types";

export interface ArchiveFilterValues {
  search: string;
  status: ArchiveStatusValue | "";
}

export const EMPTY_ARCHIVE_FILTERS: ArchiveFilterValues = { search: "", status: "" };

/** Both real `GET /reports/archive` query params (§19) — searched/filtered
 * server-side, not client-side. */
export function ArchiveFilters({ values, onChange, onReset }: { values: ArchiveFilterValues; onChange: (values: ArchiveFilterValues) => void; onReset: () => void }) {
  const activeFilterCount = [values.search, values.status].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="archive-search">Search</Label>
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input id="archive-search" value={values.search} onChange={(event) => onChange({ ...values, search: event.target.value })} placeholder="Title…" className="pl-9" />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="archive-status-filter">Status</Label>
        <Select id="archive-status-filter" value={values.status} onChange={(event) => onChange({ ...values, status: event.target.value as ArchiveStatusValue | "" })} className="w-40">
          <option value="">All statuses</option>
          {ARCHIVE_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
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
